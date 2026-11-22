// Regression test for the exit order of class_loader's statics and console_bridge's
// (ros/class_loader#252, RoboStack/robostack#243).
//
// A MultiLibraryClassLoader that is never destroyed (as with plugins held until the
// process ends, e.g. rqt) leaves its ClassLoader in class_loader's static
// ClassLoaderPtrVectorImpl. That static is created right before the ClassLoader's first
// console_bridge log, so without the fix console_bridge's output handler is destroyed
// first at exit, ~ClassLoader() then logs through it: "mutex lock failed",
// std::terminate (abort, exit code 134 on macOS). The test passes if the process exits 0.
#include <cstdio>
#include <memory>

#include "class_loader/multi_library_class_loader.hpp"

#include "base.hpp"

int main()
{
  auto * loader = new class_loader::MultiLibraryClassLoader(false);  // never destroyed
  loader->loadLibrary(PLUGIN_PATH);
  {
    auto instance = loader->createUniqueInstance<Base>("Derived");
    if (instance->value() != 42) {
      std::fprintf(stderr, "unexpected plugin value\n");
      return 1;
    }
  }
  std::printf("loaded %s; exiting with the class loader still alive\n", PLUGIN_PATH);
  return 0;
}
