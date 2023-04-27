#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>
#import <sys/stat.h>

extern void *espresso_create_context(uint64_t a1, uint64_t a2);
extern void *espresso_create_plan(void *ctx, uint64_t a2);
extern int espresso_plan_add_network(void *plan, char *path, uint64_t a3,
				     uint64_t a4[2]);
extern int espresso_plan_build(void *plan);
extern int espresso_dump_ir(void *plan, char **ppath);
extern int espresso_plan_destroy(void *plan);
extern int espresso_context_destroy(void *ctx);

typedef unsigned int ANECStatus;
extern int ANECCompile(NSDictionary *param_1, NSDictionary *param_2,
		       void (^param_3)(ANECStatus status,
				       NSDictionary *statusDictionary));

#define TMPDIR_ESPRESSO @"/tmp/tohwx/esp/"
#define TMPDIR_HWX	@"/tmp/tohwx/hwx/"

#define TO_CSTRING(nsstr) \
	((char *)[nsstr cStringUsingEncoding:NSUTF8StringEncoding])
#define TO_NSSTRING(cstr) ([NSString stringWithUTF8String:cstr])

static int mlmodel_to_espresso(NSString *espressonet)
{
	int ret = 0;
	void *ctx = espresso_create_context(0x2718LL, 0xFFFFFFFFLL);
	void *plan = espresso_create_plan(ctx, 0LL);

	uint64_t vals[2];
	ret = espresso_plan_add_network(plan, TO_CSTRING(espressonet),
					0x10010LL, vals);
	if (ret) {
		NSLog(@"espresso_plan_add_network ret %d\n", ret);
		return ret;
	}

	ret = espresso_plan_build(plan);
	if (ret) {
		NSLog(@"espresso_plan_build ret %d\n", ret);
		return ret;
	}

	char *foo = TO_CSTRING(TMPDIR_ESPRESSO);
	ret = espresso_dump_ir(plan, &foo);
	if (ret) {
		NSLog(@"espressor_dump_ir ret %d\n", ret);
		return ret;
	}

	espresso_plan_destroy(plan);
	espresso_context_destroy(ctx);

	return ret;
}

static int espresso_to_hwx(NSString *name, NSString *dst)
{
	NSDictionary *iDictionary = @{
		@"NetworkPlistName": @"net.plist",
		@"NetworkPlistPath": TMPDIR_ESPRESSO,
	};
	NSArray *plistArray = @[iDictionary];

	NSMutableDictionary *optionsDictionary =
		[NSMutableDictionary dictionaryWithCapacity:4];
	NSMutableDictionary *flagsDictionary =
		[NSMutableDictionary dictionaryWithCapacity:4];
	optionsDictionary[@"InputNetworks"] = plistArray;

	mkdir(TO_CSTRING(TMPDIR_HWX), 0755);
	optionsDictionary[@"OutputFilePath"] =
		[NSString stringWithFormat:@"%@%@/", TMPDIR_HWX, name];

	mkdir(TO_CSTRING(optionsDictionary[@"OutputFilePath"]), 0755);
	optionsDictionary[@"OutputFileName"] = @"model.hwx";

	flagsDictionary[@"TargetArchitecture"] = @"h13";

	void (^simpleBlock)(ANECStatus status, NSDictionary *statusDictionary) =
		^(ANECStatus status, NSDictionary *statusDictionary) {
			// when status != 0 dump the dictionary
			if (status)
				NSLog(@"%@", statusDictionary);
		};

	int ret = ANECCompile(optionsDictionary, flagsDictionary, simpleBlock);
	if (!ret) {
		NSString *src = [NSString
			stringWithFormat:@"%@%@",
					 optionsDictionary[@"OutputFilePath"],
					 optionsDictionary[@"OutputFileName"]];
		[[NSFileManager defaultManager] copyItemAtPath:src
							toPath:dst
							 error:nil];

		printf("tohwx: output hwx: %s\n", TO_CSTRING(dst));
	}

	return ret;
}

int main(int argc, char *argv[])
{
	if (argc != 2) {
		NSLog(@"usage: tohwx [path to mlmodel]");
		return -1;
	}

	NSURL *input = [NSURL fileURLWithPath:TO_NSSTRING(argv[1])];
	printf("tohwx: input mlmodel: %s\n",
	       TO_CSTRING([[input absoluteURL] path]));

	NSString *dir =
		[[[input absoluteURL] URLByDeletingLastPathComponent] path];
	NSString *name = [[TO_NSSTRING(argv[1]) lastPathComponent]
		stringByDeletingPathExtension];
	NSString *output = [NSString stringWithFormat:@"%@/%@.hwx", dir, name];

	NSURL *compiled = [MLModel compileModelAtURL:input error:nil];
	NSString *net = [[compiled path]
		stringByAppendingString:@"/model.espresso.net"];

	if (mlmodel_to_espresso(net)) {
		return -1;
	}

	return espresso_to_hwx(name, output);
}
