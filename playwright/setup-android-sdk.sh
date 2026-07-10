#!/bin/bash
# Android SDK 环境配置脚本

echo "正在配置 Android SDK 环境..."

# 1. 创建 Android SDK 目录
sudo mkdir -p /usr/local/android-sdk/cmdline-tools
sudo chown -R $(whoami) /usr/local/android-sdk

# 2. 链接命令行工具
sudo ln -sf /usr/local/Caskroom/android-commandlinetools/*/cmdline-tools /usr/local/android-sdk/cmdline-tools/latest

# 3. 设置环境变量
echo 'export ANDROID_HOME=/usr/local/android-sdk' >> ~/.bash_profile
echo 'export ANDROID_SDK_ROOT=$ANDROID_HOME' >> ~/.bash_profile
echo 'export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin' >> ~/.bash_profile
echo 'export PATH=$PATH:$ANDROID_HOME/platform-tools' >> ~/.bash_profile
echo 'export PATH=$PATH:$ANDROID_HOME/emulator' >> ~/.bash_profile

# 4. 使环境变量生效
source ~/.bash_profile

echo "Android SDK 环境已配置完成"
echo "ANDROID_HOME = /usr/local/android-sdk"

# 5. 检查配置
echo "验证配置:"
echo "ANDROID_HOME: $ANDROID_HOME"
ls -la /usr/local/android-sdk/cmdline-tools/latest/bin/sdkmanager