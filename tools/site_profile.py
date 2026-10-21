#!/usr/bin/env python3
"""Read an anonymous local case profile; never inspect or configure a network."""
import argparse
from datetime import date
import json
import math
from pathlib import Path
import sys


DEFAULT_PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "sysu-shenzhen-rd03v2.json"
MAX_PROFILE_BYTES = 65536


class ProfileError(ValueError):
    """A profile has invalid structure or contradicts its own declarations."""


def _object(value, keys, name):
    if type(value) is not dict or set(value) != set(keys):
        raise ProfileError(name + ": 字段集合无效")
    return value


def _number(value, name, integer=False):
    if integer:
        valid = type(value) is int
    else:
        valid = type(value) in (int, float)
    try:
        valid = valid and math.isfinite(value) and value >= 0
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ProfileError(name + ": 必须是非负有限数" + ("整数" if integer else ""))
    return value


def _boolean(value, name):
    if type(value) is not bool:
        raise ProfileError(name + ": 必须是布尔值")
    return value


def _literal_object(value, expected, name):
    _object(value, expected, name)
    if value != expected:
        raise ProfileError(name + ": 不属于此现场档案支持的匿名范围")


def validate_profile(profile):
    """Validate declarations only, without proving field evidence or network state."""
    _object(profile, ("schema_version", "site", "hardware", "authentication", "verification",
                      "observation", "measurements", "claims"), "profile")
    if type(profile["schema_version"]) is not int or profile["schema_version"] != 1:
        raise ProfileError("schema_version: 只支持版本1")
    _literal_object(profile["site"], {
        "campus": "中山大学深圳校区", "access": "学生宿舍某已测墙口", "scope": "one_wall_port"
    }, "site")
    _literal_object(profile["hardware"], {
        "model": "Xiaomi AX3000T", "variant": "RD03v2", "firmware_family": "stock",
        "firmware_version": "2.0.28", "userspace_abi": "ARM soft-float",
        "wan_interface": "eth0.1", "layout_scope": "observed_device_only"
    }, "hardware")
    authentication = _object(profile["authentication"], (
        "client", "eap_method", "eap_success_observed", "account_count", "rjv3_enabled"
    ), "authentication")
    if authentication["client"] != "MiniEAP" or authentication["eap_method"] != "MD5":
        raise ProfileError("authentication: 本档案仅描述标准MiniEAP的MD5现场")
    _boolean(authentication["eap_success_observed"], "authentication.eap_success_observed")
    _boolean(authentication["rjv3_enabled"], "authentication.rjv3_enabled")
    _number(authentication["account_count"], "authentication.account_count", integer=True)
    if authentication["account_count"] != 1 or authentication["rjv3_enabled"]:
        raise ProfileError("authentication: 本档案仅描述未启用rjv3的单账号")
    verification = _object(profile["verification"], (
        "ordinary_reboot", "cold_power_cycle", "physical_wan_replug", "active_dhcp_renewal",
        "four_devices_simultaneously_active", "cross_device_broadcast", "downstream_ipv6"
    ), "verification")
    for key, value in verification.items():
        if type(value) is not str or value not in ("passed", "failed", "not_tested"):
            raise ProfileError("verification." + key + ": 未知验收状态")
    observation = _object(profile["observation"], (
        "recorded_on", "target_seconds", "recorded_seconds", "sample_count", "private_sample_count",
        "probe_cycle_count", "successful_probe_pair_count", "service_sample_count",
        "service_online_sample_count", "gap_count", "maximum_interval_seconds", "result",
        "recording_active", "twenty_four_hours_passed", "reason", "heartbeat_active"
    ), "observation")
    try:
        if type(observation["recorded_on"]) is not str:
            raise ValueError()
        date.fromisoformat(observation["recorded_on"])
    except ValueError:
        raise ProfileError("observation.recorded_on: 日期无效") from None
    for key in ("target_seconds", "sample_count", "private_sample_count", "probe_cycle_count",
                "successful_probe_pair_count", "service_sample_count", "service_online_sample_count", "gap_count"):
        _number(observation[key], "observation." + key, integer=True)
    for key in ("recorded_seconds", "maximum_interval_seconds"):
        _number(observation[key], "observation." + key)
    if observation["target_seconds"] < 86400:
        raise ProfileError("observation.target_seconds: 24小时目标不能缩短")
    if not (observation["successful_probe_pair_count"] <= observation["probe_cycle_count"] <=
            observation["private_sample_count"] <= observation["sample_count"]):
        raise ProfileError("observation: 联网样本计数倒挂")
    if not (observation["service_online_sample_count"] <= observation["service_sample_count"] <=
            observation["private_sample_count"]):
        raise ProfileError("observation: 服务样本计数倒挂")
    if observation["gap_count"] > observation["sample_count"]:
        raise ProfileError("observation: 间隔计数倒挂")
    for key in ("recording_active", "twenty_four_hours_passed", "heartbeat_active"):
        _boolean(observation[key], "observation." + key)
    result = observation["result"]
    if type(result) is not str or result not in ("running", "completed", "interrupted", "not_started"):
        raise ProfileError("observation.result: 未知观察结果")
    if observation["recording_active"] != (result == "running"):
        raise ProfileError("observation: recording_active与结果矛盾")
    reasons = {
        "running": {"in_progress"}, "completed": {"duration_elapsed"},
        "interrupted": {"host_process_absent", "sampling_gap", "left_test_network", "probe_failures", "user_stopped"},
        "not_started": {"not_started"}
    }
    if type(observation["reason"]) is not str or observation["reason"] not in reasons[result]:
        raise ProfileError("observation.reason: 与观察结果不一致")
    if result == "not_started" and (observation["recorded_seconds"] or observation["sample_count"]):
        raise ProfileError("observation: 未开始却存在记录")
    if observation["twenty_four_hours_passed"]:
        complete = (
            result == "completed" and observation["recorded_seconds"] >= observation["target_seconds"]
            and observation["sample_count"] > 0
            and observation["successful_probe_pair_count"] == observation["probe_cycle_count"]
            == observation["private_sample_count"] == observation["sample_count"]
            and observation["service_sample_count"] > 0
            and observation["service_online_sample_count"] == observation["service_sample_count"]
            and observation["gap_count"] == 0
            and 0 < observation["maximum_interval_seconds"] <= 90
            # Allow one trailing sample interval; this checks plausibility only.
            and observation["sample_count"] >= (
                observation["target_seconds"] / observation["maximum_interval_seconds"]
            )
        )
        if not complete:
            raise ProfileError("observation: 24小时通过声明缺少完整有效样本")
    measurements = profile["measurements"]
    if type(measurements) is not list or not measurements or len(measurements) > 16:
        raise ProfileError("measurements: 必须有1至16组匿名短测")
    periods = set()
    for measurement in measurements:
        _object(measurement, ("period", "single_download", "parallel_download", "parallel_upload"), "measurement")
        period = measurement["period"]
        if type(period) is not str or period not in ("early_morning", "morning_followup") or period in periods:
            raise ProfileError("measurement.period: 未知或重复时段")
        periods.add(period)
        for key in ("single_download", "parallel_download", "parallel_upload"):
            item = _object(measurement[key], ("mbps", "connections", "bytes_per_connection"), "measurement." + key)
            _number(item["mbps"], "measurement.mbps")
            _number(item["connections"], "measurement.connections", integer=True)
            _number(item["bytes_per_connection"], "measurement.bytes_per_connection", integer=True)
            if item["connections"] < 1 or item["bytes_per_connection"] < 1:
                raise ProfileError("measurement: 连接数与字节数必须为正数")
            if (key == "single_download") != (item["connections"] == 1):
                raise ProfileError("measurement: 单连接/并发标签与连接数矛盾")
    claims = _object(profile["claims"], ("account_limit_proven", "multiple_accounts_tested"), "claims")
    for key, value in claims.items():
        _boolean(value, "claims." + key)
        if value:
            raise ProfileError("claims: 此现场未提供账号限速或多账号验证证据")
    return profile


def _pairs_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError("JSON: 存在重复字段")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ProfileError("JSON: 不允许NaN或Infinity")


def parse_profile(data):
    """Parse bounded UTF-8 JSON, reject duplicates and non-JSON numeric constants."""
    if not isinstance(data, bytes) or len(data) > MAX_PROFILE_BYTES:
        raise ProfileError("JSON: 输入类型或大小无效")
    try:
        profile = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs_without_duplicates,
                             parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ProfileError("JSON: 编码或语法无效") from None
    return validate_profile(profile)


def load_profile(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_PROFILE_BYTES + 1)
    return parse_profile(data)


def summary(profile):
    """Return only a fixed anonymous summary, not arbitrary input fields."""
    validate_profile(profile)
    observation = profile["observation"]
    return {
        "schema_version": 1,
        "scope": "one_wall_port",
        "campus": "中山大学深圳校区",
        "firmware": "RD03v2 stock 2.0.28",
        "authentication": "MiniEAP / EAP-MD5 / single account",
        "ordinary_reboot": profile["verification"]["ordinary_reboot"],
        "verification": dict(profile["verification"]),
        "observation": dict(observation),
        "measurements": profile["measurements"],
        "account_limit_proven": False,
        "multiple_accounts_tested": False,
        "consistency_only": True,
        "network_verified_by_this_tool": False
    }


def chinese_report(value):
    observation = value["observation"]
    seconds = int(observation["recorded_seconds"])
    duration = "%d小时%d分%d秒" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)
    state = {"running": "记录中", "completed": "计时结束", "interrupted": "记录中断", "not_started": "未开始"}
    reasons = {"host_process_absent": "电脑观察进程不存在", "sampling_gap": "采样间隔异常",
               "left_test_network": "离开测试网络", "probe_failures": "联网探测失败", "user_stopped": "用户停止",
               "in_progress": "尚在观察", "duration_elapsed": "观察计时结束", "not_started": "尚未开始"}
    lines = [
        "中山大学深圳校区学生宿舍某墙口：匿名现场档案",
        "范围：仅已测RD03v2原厂2.0.28；接口与ABI不能推广到其他设备。",
        "认证：标准MiniEAP、EAP-MD5、单账号；未启用rjv3。",
        "普通重启验收：" + {"passed": "已通过", "failed": "失败", "not_tested": "未测试"}[value["ordinary_reboot"]],
        "观察：%s，进程报告累计观测时长%s；原因：%s。" % (state[observation["result"]], duration, reasons[observation["reason"]]),
        "双站通过：%d/%d；服务在线：%d/%d；间隔异常：%d。" % (
            observation["successful_probe_pair_count"], observation["probe_cycle_count"],
            observation["service_online_sample_count"], observation["service_sample_count"], observation["gap_count"]),
        "24小时验收：" + ("档案声明通过" if observation["twenty_four_hours_passed"] else "尚未完成完整24小时验收"),
    ]
    names = {"early_morning": "凌晨短测", "morning_followup": "上午短测"}
    for measurement in value["measurements"]:
        lines.append("%s：单连接下载%.3f、并发下载%.3f、并发上传%.3f Mbps。" % (
            names[measurement["period"]], measurement["single_download"]["mbps"],
            measurement["parallel_download"]["mbps"], measurement["parallel_upload"]["mbps"]))
    pending_names = {"cold_power_cycle": "冷启动", "physical_wan_replug": "物理WAN拔插",
                     "active_dhcp_renewal": "主动续租", "four_devices_simultaneously_active": "四台同时",
                     "cross_device_broadcast": "跨设备广播", "downstream_ipv6": "下游IPv6"}
    pending = [name for key, name in pending_names.items() if value["verification"][key] == "not_tested"]
    lines.append("没有证实账号限速，未测试多账号；短测不代表持续上限。")
    if pending:
        lines.append("待分别验收：" + "、".join(pending) + "。")
    lines.extend(("样本和累计时长不能证明每秒连续联网。",
                  "本工具仅检查档案声明一致性，不访问网络、不验证凭据或设备当前状态。"))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读匿名深圳现场档案并检查声明一致性；不访问网络或设备。")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="本地JSON档案；默认使用仓库随附档案")
    parser.add_argument("--json", action="store_true", help="输出固定匿名summary JSON")
    arguments = parser.parse_args(argv)
    try:
        value = summary(load_profile(arguments.profile))
    except (OSError, ProfileError):
        print("档案读取或一致性校验失败；未访问网络或设备。", file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2) if arguments.json else chinese_report(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
