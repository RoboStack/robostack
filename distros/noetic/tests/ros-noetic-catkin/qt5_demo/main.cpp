#include <QCoreApplication>
#include <QRegExp>
#include "widget.h"
int main(int argc, char** argv)
{
  QCoreApplication app(argc, argv);
  QRegExp re("ro.*stack");
  return re.exactMatch("robostack") ? 0 : 1;
}
