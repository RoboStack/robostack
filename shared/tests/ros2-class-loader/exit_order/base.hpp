#ifndef BASE_HPP_
#define BASE_HPP_

class Base
{
public:
  virtual ~Base() = default;
  virtual int value() const = 0;
};

#endif  // BASE_HPP_
