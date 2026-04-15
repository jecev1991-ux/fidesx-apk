[app]
title = FIDESx
package.name = fidesx
package.domain = org.fidesx
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 9.0
requirements = python3,kivy==2.2.0,websocket-client,requests
orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0
android.permissions = INTERNET
android.api = 31
android.minapi = 21
android.ndk = 25b
android.arch = arm64-v8a
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
