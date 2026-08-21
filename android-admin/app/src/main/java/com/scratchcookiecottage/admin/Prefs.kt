package com.scratchcookiecottage.admin

import android.content.Context
import android.webkit.CookieManager

object Prefs {
    private const val FILE = "scc_admin"
    private const val KEY_BASE_URL = "base_url"
    const val DEFAULT_URL = "https://scratchcookiecottage.pythonanywhere.com"
    const val DEFAULT_PUSH_SECRET = "c3fd997f3ec7c56f0ca681e4d151cec6"

    fun baseUrl(context: Context): String {
        val stored = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .getString(KEY_BASE_URL, "")
            .orEmpty()
            .trim()
            .trimEnd('/')
        if (stored.isEmpty() || stored.contains("192.168.") || stored.contains("127.0.0.1")) {
            return DEFAULT_URL
        }
        return stored
    }

    fun setBaseUrl(context: Context, url: String) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_BASE_URL, url.trim().trimEnd('/'))
            .apply()
    }

    fun pushSecret(context: Context): String {
        val stored = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .getString("push_secret", "")
            .orEmpty()
            .trim()
        return stored.ifEmpty { DEFAULT_PUSH_SECRET }
    }

    fun setPushSecret(context: Context, secret: String) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit()
            .putString("push_secret", secret.trim())
            .apply()
    }

    fun adminUrl(context: Context): String {
        val base = baseUrl(context)
        if (base.isEmpty()) return ""
        return "$base/admin"
    }

    fun writeAppGateCookie(context: Context) {
        val base = baseUrl(context)
        val secret = pushSecret(context)
        if (base.isEmpty() || secret.isEmpty()) return
        val cookies = CookieManager.getInstance()
        cookies.setAcceptCookie(true)
        val secure = if (base.startsWith("https", ignoreCase = true)) "; Secure" else ""
        cookies.setCookie(base, "scc_app=$secret; Path=/$secure")
        cookies.flush()
    }
}
