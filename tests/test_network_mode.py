from network_mode import classify_network


def test_standalone_ap_is_offline_capable_without_uplink():
    status = classify_network(
        wlan_mode="AP",
        default_interface=None,
        addresses={"wlan0": ["192.168.50.1"]},
    )
    assert status.mode == "standalone_ap"
    assert status.ap_active is True
    assert status.uplink_configured is False


def test_ap_with_wired_default_route_is_uplink_mode():
    status = classify_network(
        wlan_mode="AP",
        default_interface="enP4p65s0",
    )
    assert status.mode == "ap_uplink"
    assert status.uplink_interface == "enP4p65s0"


def test_managed_default_route_is_same_lan_mode():
    status = classify_network(wlan_mode="managed", default_interface="wlan0")
    assert status.mode == "same_lan"
    assert status.ap_active is False


def test_ethernet_default_route_is_wired_lan_mode():
    status = classify_network(wlan_mode=None, default_interface="enP4p65s0")
    assert status.mode == "wired_lan"
    assert status.label == "有线局域网"
    assert status.uplink_interface == "enP4p65s0"


def test_static_ethernet_without_default_route_is_still_wired_lan():
    status = classify_network(
        wlan_mode=None,
        default_interface=None,
        addresses={"enP4p65s0": ["192.168.1.109"]},
    )
    assert status.mode == "wired_lan"
    assert status.uplink_configured is False


def test_no_ap_and_no_default_route_is_offline():
    status = classify_network(wlan_mode=None, default_interface=None)
    assert status.mode == "offline"
    assert status.label == "未连接网络"
