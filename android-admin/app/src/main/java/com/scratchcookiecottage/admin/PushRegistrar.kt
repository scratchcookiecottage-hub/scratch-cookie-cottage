package com.scratchcookiecottage.admin

import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

object PushRegistrar {
    fun register(context: Context) {
        val appContext = context.applicationContext
        thread {
            try {
                if (FirebaseApp.getApps(appContext).isEmpty()) {
                    FirebaseApp.initializeApp(appContext)
                }
                if (FirebaseApp.getApps(appContext).isEmpty()) return@thread
                FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                    sendToken(appContext, token)
                }
            } catch (ex: Exception) {
                Log.w("SCCPush", "Firebase not ready", ex)
            }
        }
    }

    fun sendToken(context: Context, token: String) {
        val secret = Prefs.pushSecret(context)
        val base = Prefs.baseUrl(context)
        if (secret.isEmpty() || base.isEmpty() || token.isEmpty()) return
        thread {
            try {
                val url = URL("$base/api/push-token")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 15000
                conn.readTimeout = 15000
                val body = JSONObject()
                    .put("token", token)
                    .put("secret", secret)
                    .toString()
                OutputStreamWriter(conn.outputStream).use { it.write(body) }
                conn.inputStream.use { it.readBytes() }
                conn.disconnect()
            } catch (ex: Exception) {
                Log.w("SCCPush", "Could not register token", ex)
            }
        }
    }
}
