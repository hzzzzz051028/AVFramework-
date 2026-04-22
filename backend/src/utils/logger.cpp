#include "utils/logger.h"
#include <iostream>

namespace avframework {

std::ofstream Logger::log_file_;
std::mutex Logger::log_mutex_;
Logger::Level Logger::min_level_ = Logger::Level::Info;

void Logger::init(const std::string& filename) {
    std::lock_guard<std::mutex> lock(log_mutex_);
    if (log_file_.is_open()) {
        log_file_.close();
    }
    log_file_.open(filename, std::ios::out | std::ios::app);
}

void Logger::debug(const std::string& message) {
    log(Level::Debug, message);
}

void Logger::info(const std::string& message) {
    log(Level::Info, message);
}

void Logger::warn(const std::string& message) {
    log(Level::Warn, message);
}

void Logger::error(const std::string& message) {
    log(Level::Error, message);
}

void Logger::log(Level level, const std::string& message) {
    if (level < min_level_) {
        return;
    }

    std::lock_guard<std::mutex> lock(log_mutex_);

    std::string log_line = "[" + getCurrentTime() + "] "
                         + "[" + levelToString(level) + "] "
                         + message;

    if (log_file_.is_open()) {
        log_file_ << log_line << std::endl;
        log_file_.flush();
    }

    if (level >= Level::Warn) {
        std::cerr << log_line << std::endl;
    } else {
        std::cout << log_line << std::endl;
    }
}

std::string Logger::getCurrentTime() {
    auto now = std::chrono::system_clock::now();
    auto time = std::chrono::system_clock::to_time_t(now);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()) % 1000;

    std::ostringstream oss;
    oss << std::put_time(std::localtime(&time), "%Y-%m-%d %H:%M:%S");
    oss << '.' << std::setfill('0') << std::setw(3) << ms.count();

    return oss.str();
}

std::string Logger::levelToString(Level level) {
    switch (level) {
        case Level::Debug: return "DEBUG";
        case Level::Info:  return "INFO ";
        case Level::Warn:  return "WARN ";
        case Level::Error: return "ERROR";
        default:           return "UNKNOWN";
    }
}

}
