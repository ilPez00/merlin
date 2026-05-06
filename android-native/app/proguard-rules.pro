# OkHttp
-dontwarn okhttp3.**
-keep class okhttp3.** { *; }

# Keep JSON parsing
-keepattributes Signature
-keep class com.google.gson.** { *; }
