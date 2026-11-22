#include <rtabmap/core/Compression.h>
#include <rtabmap/core/Features2d.h>
#include <cstdio>
int main()
{
  // compressed images and point clouds keep their OpenCV 4 type encoding (upstream
  // bcdb4b4546): a CV_32FC2 matrix comes back with its type
  cv::Mat m(4, 5, CV_32FC2, cv::Scalar(1, 2));
  cv::Mat u = rtabmap::uncompressData(rtabmap::compressData2(m));
  if (u.type() != m.type() || cv::norm(u - m) != 0) {
    std::printf("compressData round trip: type %d, expected %d\n", u.type(), m.type());
    return 1;
  }
  rtabmap::Feature2D * orb = rtabmap::Feature2D::create(rtabmap::Feature2D::kFeatureOrb);
  cv::Mat image(240, 320, CV_8UC1);
  cv::randu(image, 0, 255);
  bool ok = !orb->generateKeypoints(image).empty();
  delete orb;
  return ok ? 0 : 1;
}
