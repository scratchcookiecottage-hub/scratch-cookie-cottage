package com.scratchcookiecottage.admin

import android.content.Context

object Prefs {
    private const val FILE = "scc_admin"
    private const val KEY_BASE_URL = "base_url"
    const val DEFAULT_URL = "https://scratchcookiecottage.pythonanywhere.com"

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

    fun adminUrl(context: Context): String {
        val base = baseUrl(context)
        if (base.isEmpty()) return ""
        return "$base/admin"
    }
}
