#pragma once

#include <string>
#include <unordered_map>
#include <fstream>

namespace avframework {

class Config {
public:
    Config() = default;

    bool load(const std::string& filename);
    bool save(const std::string& filename);

    int getInt(const std::string& key, int default_value = 0) const;
    double getDouble(const std::string& key, double default_value = 0.0) const;
    std::string getString(const std::string& key, const std::string& default_value = "") const;
    bool getBool(const std::string& key, bool default_value = false) const;

    void setInt(const std::string& key, int value);
    void setDouble(const std::string& key, double value);
    void setString(const std::string& key, const std::string& value);
    void setBool(const std::string& key, bool value);

    bool has(const std::string& key) const;

private:
    std::unordered_map<std::string, std::string> values_;
};

}
