#include <optional>
#include <Eigen/Core>
#include <boost/system/error_code.hpp>
#include <boost/thread.hpp>
int main()
{
  static_assert(__cplusplus >= 201703L, "built below C++17");
  std::optional<Eigen::Vector3d> v = Eigen::Vector3d::Ones();
  boost::system::error_code ec;
  return (v->sum() == 3.0 && !ec) ? 0 : 1;
}
