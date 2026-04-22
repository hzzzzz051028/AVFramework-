#pragma once

#include <string>
#include <fstream>
#include <mutex>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace avframework {

class Logger {
public:
    enum class Level {
        Debug,
        Info,
        Warn,
        Error
    };

    static void init(const std::string& filename = "avframework.log");
    static void setLevel(Level level) { min_level_ = level; }

    static void debug(const std::string& message);
    static void info(const std::string& message);
    static void warn(const std::string& message);
    static void error(const std::string& message);

    static void log(Level level, const std::string& message);

private:
    static std::string getCurrentTime();
    static std::string levelToString(Level level);

    static std::ofstream log_file_;
    static std::mutex log_mutex_;
    static Level min_level_;
};

}
