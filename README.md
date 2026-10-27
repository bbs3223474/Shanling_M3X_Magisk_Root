### 【本Repo所有代码，以及本README均由Deepseek Harness开发实现，所有代码均为AI生成，欢迎各位审阅，本人不对此Repo的引用、转载、修改、重发布做任何限制和版权声明】

# 山灵 M3X (msm8937 / Android 7.1.1) root 与系统改造记录

## 0. 结果概览

| 项目 | 状态 |
|---|---|
| Root (Magisk 27.0) | ✅ 已生效，`su -c id` → `uid=0 context=u:r:magisk:s0` |
| 开机默认桌面不再弹框 | ✅ 已修复，开机自动进入 Nova |
| 无障碍服务可启用 | ✅ 可用脚本控制（菜单 UI 无法恢复） |
| fastboot flash 恢复 | ❌ 不可行（见 §L1） |
| 第三方 recovery (TWRP) | ⚠️ 不可直接移植（见 §L2），已完成完整备份 + 可用刷机通道 |

设备：`Shanling_M3X`，`msm8937_64`，`ro.build.type=user`，`veritymode=enforcing`，`crypto.state=unencrypted`。

---

## 1. Root 是怎么拿到的（关键原理）

设备 bootloader 被阉割（fastboot 只有 `getvar` / `download`），recovery 又强制校验 OTA 签名，
但 **OTA 包的 `META-INF/com/android/otacert` 是 AOSP 测试密钥（testkey）**，说明整机用 testkey 签名。

于是可以自签 OTA：

1. 官方 OTA 用的是 recovery 的 **whole-file signature**（不是 JAR 签名），文件尾部结构为：

   ```
   [zip 数据][u16 注释长度] "signed by SignApk\0" [PKCS#7 DER] [u16 DER长度+6][0xFFFF][u16 注释长度]
   ```

   签名覆盖范围是 `file[0 : EOF-注释长度-2]`，算法 `SHA1 + RSA PKCS#1 v1.5`。

2. `tools/otasign.py` 用 AOSP `testkey.pk8` 复现该签名。**自检结果：对官方 1.75 包生成出的签名与官方签名逐字节一致**，
   证明签名实现与 SignApk 完全等价。

3. 用该密钥签了一个只写 `boot` 分区的 OTA，放入 `/storage/emulated/0/`，通过
   「系统升级 → 本地升级」触发 `RecoverySystem.installPackage()`，recovery 校验通过并写入 Magisk 补丁版 boot。

产物：
- `out/m3x_magisk_boot.zip` —— 刷入 Magisk 版 boot（已使用）
- `out/m3x_stock_boot.zip`  —— 回滚官方 boot（已放到设备 `/storage/emulated/0/update.zip`）

> 安全网：recovery 的「Apply update from SD card」固定读取 `/sdcard/update.zip`，
> 所以该位置放的是**官方 boot 回滚包**，即使系统起不来也能在不接电脑的情况下救回。

---

## L1. 关于「fastboot 命令缺失」——结论：无法恢复

证据：

- `fastboot getvar all` 正常；`fastboot flash/boot/reboot/continue/oem` 一律 `unknown command`。
- `flash boot` 时 `Sending 'boot.img' ... OKAY` 后 `Writing 'boot' FAILED (remote: 'unknown command')`
  —— 说明 LK 实现了 `download:`（收数据）但**没有 `flash:` 命令**。
- 反汇编 aboot 字符串：存在 `flash_write_image`、`Cannot flash: image header corrupt` 等写 flash 的代码，
  但 fastboot 命令表里只有 `getvar:` / `download:`，`flash:` / `boot:` / `reboot:` 的字符串根本不存在，
  说明相关命令与处理函数在编译时就被裁掉（linker GC），**不是被锁，而是没编进去**。

因此：改 `devinfo` 解锁、`fastboot oem unlock` 都不会让 flash 出现。唯一真正的办法是换一个功能完整的
aboot（`emmc_appsboot.mbn`）。风险极高：aboot 写错 = 连 fastboot/EDL 都进不去，属于硬砖，只能靠 EDL(9008) + firehose 救。
当前 `getvar` 显示 `secure:no`，理论上 aboot 不受签名链校验，但没有匹配的 aboot 二进制，不建议动。

**替代方案（已提供）**：有了 root，刷分区不需要 fastboot。

```sh
# 查看分区
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-flash.sh list"
# 备份 boot / recovery / aboot
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-flash.sh backup boot /storage/emulated/0/boot_backup.img"
# 刷写
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-flash.sh flash boot /storage/emulated/0/boot.img"
```

等价于 `fastboot flash <part> <img>`，且不受 bootloader 限制。

---

## L2. 关于「第三方 recovery」

现状分析（`recovery_stock.img`，从 `/dev/block/bootdevice/by-name/recovery` 完整导出，64MB）：

- 标准 AOSP recovery（boot image 格式，kernel + ramdisk，`sbin/recovery` 1.4MB）
- `res/keys` 为 OTA 校验公钥（即 testkey 体系）
- `init.rc` 中 adbd 为 `--device_banner=recovery`，`ALLOW_ADBD_ROOT=0`，因此 recovery 里也拿不到 root shell

为什么不能直接刷个 TWRP：

- TWRP 是**按机型编译**的（device tree 定义 fstab、屏幕、触摸、按键、分区布局），
  没有 M3X 的 device tree 和内核源码，拿别的 msm8937 机型（如红米 4）的 TWRP 刷进去 =
  黑屏/触摸失效/找不到分区，且可能连带把 recovery 搞坏。
- 移植需要：Linux 编译环境 + TWRP(7.1 分支) 源码 + 该机内核/device tree，属于独立的长周期工程。

已完成的实事：

- 完整备份 recovery：`recovery_stock.img`（可随时 `m3x-flash.sh flash recovery recovery_stock.img` 还原）
- 打通了「任意签名 OTA」通道：等于把 stock recovery 变成了**可以刷自签包**的 recovery
  （第三方包只要能被重新签名/或改用 dd 刷写，就不受签名限制）

如果后续确实要 TWRP，建议路线：先备份全分区 → 提取内核 config/dtb → 建 device tree → 云编译。

---

## L3. 关于「设置里没有无障碍」

根因（已确认，不是隐藏，是**被删掉了**）：

- `am start -a android.settings.ACCESSIBILITY_SETTINGS` 无法解析
- `com.android.settings/.Settings$AccessibilitySettingsActivity`、`.accessibility.AccessibilitySettings`
  显式启动均报 `Activity class ... does not exist`
- Settings 里只剩 `AccessibilityDaltonizerSettingsActivity`（色彩校正）

但 `AccessibilityManagerService` 是完好的，所以**服务层可以正常启用**，只是没有 UI 入口。

已提供脚本（等价于设置里的开关）：

```sh
# 查看
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-a11y.sh list"
# 启用 TalkBack
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-a11y.sh enable com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService"
# 关闭全部
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-a11y.sh off"
```

实测：TalkBack 能被 `dumpsys accessibility` 识别为已绑定服务（`Service[label=TalkBack ...]`），功能正常。

要恢复「设置 → 无障碍」这个菜单本身，只能改 `Settings.apk`（反编译 + 补 activity + 重打包 + 平台签名），
当前环境没有 apktool/JDK，未做。可以用脚本/快捷方式替代。

---

## L4. 关于「默认桌面每次都问」——已修复

根因（logcat 实锤）：

```
D/ActivityManager: DefaultLauncher ::: ComponentInfo{com.android.launcher3/com.android.launcher3.Launcher}
I/PackageManager: Replacing preferred activity com.android.launcher3/.Launcher for user 0
I/ActivityManager: START ... ResolverActivity ... from uid 0
```

- ROM 改了 framework：`ActivityManagerService` 在 `systemReady()` 里**硬编码**把默认桌面替换成
  `com.android.launcher3/.Launcher`（services.odex 里就是写死的字符串常量），每次开机都覆盖用户的「始终」选择。
- 而 `com.android.launcher3` 又被禁用（`enabled=3`），于是这个强制偏好失效 → 系统弹 `ResolverActivity` 选择框。
- 顺带发现：这个 ROM 还魔改了 `cmd package set-home-activity`（AOSP 7.1 原生没有），但只写内存，重启即被覆盖。

解决方案（已落地为 Magisk 模块 `m3x_launcher_fix`）：

1. **彻底移除 Launcher3**：模块用 systemless 覆盖把 `/system/priv-app/Launcher3/Launcher3.apk`
   替换成一个空文件，包管理器扫描不到这个包（`pm path com.android.launcher3` 无输出）。
   不改动 /system 真实分区，删掉模块即可还原，也不影响以后用官方 OTA。
2. **保留原厂的「安卓模式 / 纯净模式」磁贴**（`androidpure_mode`，写入
   `Settings.System["system.audio.shanling.AndroidPureMode"]`），由守护进程 `m3x-home-watch.sh` 跟随该值：
   - `0` 安卓模式 → Nova
   - `1` 纯净模式 → 山灵音乐（与原厂行为完全一致，没有改动）
   守护进程用 `setsid` 脱离 Magisk 的生命周期，开机后持续重试直到桌面真正显示，之后再按值变化实时切换。
3. `post-fs-data.sh` 在 PackageManagerService 启动前预写入 Nova 偏好，缩短 framework 强制 launcher3 失败后的空窗。

实测：重启后无 Launcher3、无选择框，直接进入 Nova（约 t+40s，随系统启动完成）；
下拉磁贴切纯净模式 → 山灵音乐；切回安卓模式 → Nova。

手动切换（脚本方式，等价于磁贴）：

```sh
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-home.sh music"  # 山灵音乐
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-home.sh nova"   # Nova
```

或在 Magisk App → 模块 → `M3X Launcher Fix` → 操作按钮（点一下切换，立即生效）。

注：framework 仍会尝试把默认桌面设成（已不存在的）launcher3，因此开机早期可能出现 1~2 秒的
`FallbackHome`/选择框空窗，守护进程会立刻顶掉；这是保持 Launcher3 被删除的代价。

### 换成别的第三方 Launcher（不限于 Nova）

这套机制与 Nova 无关：ROM 只硬编码了 `com.android.launcher3`，把它移除后，桌面由守护进程按
`/data/adb/m3x_android_home` 里配置的组件来设置。装好新 Launcher 后：

```sh
# 1) 看它注册的 HOME 组件（name= 那一行就是 pkg/activity 的简写形式）
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-home.sh list"

# 2) 设为「安卓模式」的桌面（立即生效，且重启后保持）
adb shell su -c "sh /data/adb/modules/m3x_launcher_fix/m3x-home.sh set com.example.launcher/.MainActivity"
```

- `set` 会先校验该包已安装，再写入 `/data/adb/m3x_android_home`
- 旧 Launcher 可以留着不卸载，不会因此再弹选择框
- 若配置的 Launcher 被卸载，守护进程会自动回退到 Nova
- 纯净模式始终固定为山灵音乐，与配置无关

实测：把目标临时改成 `com.shanling.MusicApp/.MainActivity`，Home 立刻切到音乐播放器；
改回 Nova 也立刻生效，证明目标是运行时可替换的。

---

## 2. 文件清单（PC）

```
D:\Desktop\m3x_root\
├─ out\m3x_magisk_boot.zip      Magisk 版 boot 的 testkey 签名 OTA（已刷入）
├─ out\m3x_stock_boot.zip       官方 boot 回滚 OTA（= 设备 /storage/emulated/0/update.zip）
├─ out\m3x_probe.zip            仅验证签名、不写分区的探测包
├─ keys\testkey.pk8             AOSP 测试私钥
├─ keys\pkcs7_template.der      PKCS#7 模板（与官方包结构一致）
├─ boot_stock.img               官方 boot
├─ magisk_patched.img           Magisk App 生成的补丁 boot
├─ recovery_stock.img           官方 recovery 完整备份（64MB）
├─ aboot.img                    当前 aboot 备份（1MB）
├─ module\                      m3x_launcher_fix 模块源码
│  ├─ module.prop
│  ├─ post-fs-data.sh           开机前预写 Nova 偏好
│  ├─ service.sh                以 setsid 启动守护进程
│  ├─ m3x-home-watch.sh         监听安卓/纯净模式并切换桌面
│  ├─ m3x-home.sh               手动切换桌面
│  ├─ m3x-a11y.sh               无障碍服务开关
│  ├─ m3x-flash.sh              分区备份/刷写
│  └─ system\priv-app\Launcher3\Launcher3.apk   (0 字节，用于屏蔽 Launcher3)
└─ tools\
   ├─ otasign.py                whole-file OTA 签名（与 SignApk 等价）
   ├─ build_ota.py              生成并签名 OTA
   ├─ bootimg.py / ramdisk.py   boot/ramdisk 解析
   └─ （其余为诊断脚本 diag*.sh）
```

## 3. 风险与回滚

- 不要刷 aboot / sbl / tz 等引导链分区，写错即硬砖。
- boot 出问题：进 recovery（你已知按键组合）→「Apply update from SD card」→ 刷 `/sdcard/update.zip`（官方 boot）。
- 想彻底还原：`m3x-flash.sh flash boot boot_stock.img` + 在 Magisk App 里卸载 Magisk。
- 想恢复 Launcher3：删除 `/data/adb/modules/m3x_launcher_fix/system/priv-app/Launcher3/` 后重启即可（systemless，不动 /system）。
- OTA 大版本升级会覆盖 boot → root 丢失，升级后需重新用 `m3x_magisk_boot.zip` 刷一次（或在 Magisk 里「安装到未使用的分区/直接安装」）。
- 若 OTA 升级重置了桌面相关状态，重启一次即可让模块重新接管。
