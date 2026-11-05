#include <gmock/gmock.h>
struct Foo { virtual ~Foo() = default; virtual int get() = 0; };
struct MockFoo : Foo { MOCK_METHOD(int, get, (), (override)); };
TEST(Mock, Works) { MockFoo m; EXPECT_CALL(m, get()).WillOnce(::testing::Return(3)); EXPECT_EQ(m.get(), 3); }
