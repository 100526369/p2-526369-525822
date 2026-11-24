
#ifndef ESTADO_HPP
#define ESTADO_HPP

#include <array>
#include <cstddef>
#include <functional>
#include <stdexcept>
#include <string_view>
#include <cctype>
#include <cmath>
#include <algorithm>



namespace airport_search {

constexpr double EARTH_RADIUS_KM = 6371.0;
constexpr double PI = 3.14159265358979323846;

class AirportState {
public:
    AirportState(
        std::string_view code,
        double latitude,
        double longitude
    ): latitude_(latitude), longitude_(longitude)
    {
        if (code.size() != 3) {
            throw std::invalid_argument(
                "IATA must contain exactly 3 characters"
            );
        }

        // Codes are normalized to uppercase so that equality and hashing
        // are consistent no matter where the code came from.
        for (std::size_t i = 0; i < 3; ++i) {
            IATA_[i] = static_cast<char>(
                std::toupper(static_cast<unsigned char>(code[i]))
            );
        }
    }

    // Read-only accessors
    std::string_view get_IATA() const {
        return {IATA_.data(), IATA_.size()};
    }

    double get_latitude() const {
        return latitude_;
    }

    double get_longitude() const {
        return longitude_;
    }

    // Equality based only on IATA
    bool operator==(const AirportState& other) const {
        return IATA_ == other.IATA_;
    }

private:
    std::array<char, 3> IATA_;
    double latitude_;
    double longitude_;
};

// Converts degrees to radians
inline double to_radians(double degrees) {
    return degrees * PI / 180.0;
}

// Haversine distance between two airports (in km) its the cost of the fly operator
inline double haversine(
    const AirportState& a,
    const AirportState& b
) {
    const double lat1 = to_radians(a.get_latitude());
    const double lat2 = to_radians(b.get_latitude());

    const double lon1 = to_radians(a.get_longitude());
    const double lon2 = to_radians(b.get_longitude());

    const double dlat = lat2 - lat1;
    const double dlon = lon2 - lon1;

    const double arg = (std::sin(dlat / 2.0)*std::sin(dlat / 2.0)) + std::cos(lat1) * std::cos(lat2) * (std::sin(dlon / 2.0)*std::sin(dlon / 2.0));

    // Protect against floating-point rounding errors
    const double bounded_h = std::clamp(arg, 0.0, 1.0);

    const double central_angle =
        2.0 * std::asin(std::sqrt(bounded_h));

    return EARTH_RADIUS_KM * central_angle;
}

} // namespace airport_search


namespace std {

template <>
struct hash<airport_search::AirportState> {

    std::size_t operator()(
        const airport_search::AirportState& airport
    ) const noexcept {
        return std::hash<std::string_view>{}(
            airport.get_IATA()
        );
    }
};

} // namespace std

#endif // ESTADO_HPP

