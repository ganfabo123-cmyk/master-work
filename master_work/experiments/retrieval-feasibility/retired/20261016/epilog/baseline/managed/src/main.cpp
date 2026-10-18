#include <iostream>
#include <string>

int main() {
    std::string line;
    int facts = 0;
    while (std::getline(std::cin, line)) {
        if (line == "halt.") break;
        if (!line.empty()) ++facts;
    }
    std::cout << "Epilog fixture ready; facts=" << facts << "\n";
    return 0;
}
