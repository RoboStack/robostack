#include <opencv2/calib3d.hpp>
#include <opencv2/features2d.hpp>
#include <opencv2/imgproc.hpp>
int main()
{
  // calib3d (Rodrigues), imgproc (getRotationMatrix2D, cvtColor) and features2d (ORB)
  cv::Mat rotation;
  cv::Rodrigues(cv::Vec3d(0, 0, CV_PI / 2), rotation);
  cv::Mat affine = cv::getRotationMatrix2D(cv::Point2f(0, 0), 90, 1);
  cv::Mat color(64, 64, CV_8UC3, cv::Scalar(10, 20, 30)), gray;
  cv::cvtColor(color, gray, cv::COLOR_BGR2GRAY);
  std::vector<cv::KeyPoint> keypoints;
  cv::ORB::create()->detect(gray, keypoints);
  return (rotation.rows == 3 && affine.cols == 3 && gray.channels() == 1) ? 0 : 1;
}
