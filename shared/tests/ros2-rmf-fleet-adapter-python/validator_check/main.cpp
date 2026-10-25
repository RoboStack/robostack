// Temporary diagnostic: rmf_task_sequence builds this validator during static
// initialisation; on Windows (lyrical) that fails. Show what is thrown.
#include <fstream>
#include <iostream>
#include <nlohmann/json-schema.hpp>

int main(int, char** argv)
{
  try
  {
    std::ifstream f(argv[1]);
    const nlohmann::json schema = nlohmann::json::parse(f);
    std::cout << "parsed schema" << std::endl;
    nlohmann::json_schema::json_validator validator(schema);
    std::cout << "validator constructed" << std::endl;
  }
  catch (const std::exception& e)
  {
    std::cout << "exception: " << e.what() << std::endl;
    return 1;
  }
  return 0;
}
