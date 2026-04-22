#include "utils/config.h"
#include <sstream>
#include <iostream>

namespace avframework {

bool Config::load(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        return false;
    }

    std::string line;
    while (std::getline(file, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }

        size_t pos = line.find('=');
        if (pos != std::string::npos) {
            std::string key = line.substr(0, pos);
            std::string value = line.substr(pos + 1);

            while (!key.empty() && (key.back() == ' ' || key.back() == '\t')) {
                key.pop_back();
            }
            while (!value.empty() && (value.front() == ' ' || value.front() == '\t')) {
                value.erase(0, 1);
            }

            values_[key] = value;
        }
    }

    return true;
}

bool Config::save(const std::string& filename) {
    std::ofstream file(filename);
    if (!file.is_open()) {
        return false;
    }

    for (const auto& [key, value] : values_) {
        file << key << " = " << value << "\n";
    }

    return true;
}

int Config::getInt(const std::string& key, int default_value) const {
    auto it = values_.find(key);
    if (it == values_.end()) {
        return default_value;
    }

    try {
        return std::stoi(it->second);
    } catch (...) {
        return default_value;
    }
}

double Config::getDouble(const std::string& key, double default_value) const {
    auto it = values_.find(key);
    if (it == values_.end()) {
        return default_value;
    }

    try {
        return std::stod(it->second);
    } catch (...) {
        return default_value;
    }
}

std::string Config::getString(const std::string& key, const std::string& default_value) const {
    auto it = values_.find(key);
    if (it == values_.end()) {
        return default_value;
    }
    return it->second;
}

bool Config::getBool(const std::string& key, bool default_value) const {
    auto it = values_.find(key);
    if (it == values_.end()) {
        return default_value;
    }

    std::string value = it->second;
    for (auto& c : value) {
        c = std::tolower(c);
    }

    return value == "true" || value == "1" || value == "yes";
}

void Config::setInt(const std::string& key, int value) {
    values_[key] = std::to_string(value);
}

void Config::setDouble(const std::string& key, double value) {
    values_[key] = std::to_string(value);
}

void Config::setString(const std::string& key, const std::string& value) {
    values_[key] = value;
}

void Config::setBool(const std::string& key, bool value) {
    values_[key] = value ? "true" : "false";
}

bool Config::has(const std::string& key) const {
    return values_.find(key) != values_.end();
}

}
