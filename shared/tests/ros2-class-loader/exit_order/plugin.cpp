#include "class_loader/class_loader.hpp"

#include "base.hpp"

class Derived : public Base
{
public:
  int value() const override {return 42;}
};

CLASS_LOADER_REGISTER_CLASS(Derived, Base)
