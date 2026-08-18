package com.scratchcookiecottage.admin

import android.Manifest
import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.CookieManager
import android.webkit.URLUtil
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.scratchcookiecottage.admin.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val notifyPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)
        requestNotificationPermission()
        PushRegistrar.register(this)

        val web = binding.webView
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)

        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.builtInZoomControls = true
        web.settings.displayZoomControls = false
        web.settings.loadWithOverviewMode = true
        web.settings.useWideViewPort = true

        web.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
            try {
                val request = DownloadManager.Request(Uri.parse(url))
                request.setMimeType(mimeType)
                request.addRequestHeader("User-Agent", userAgent)
                val cookie = CookieManager.getInstance().getCookie(url)
                if (!cookie.isNullOrBlank()) {
                    request.addRequestHeader("Cookie", cookie)
                }
                val name = URLUtil.guessFileName(url, contentDisposition, mimeType)
                request.setTitle(name)
                request.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED,
                )
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name)
                val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
                dm.enqueue(request)
                Toast.makeText(this, "Downloading $name", Toast.LENGTH_SHORT).show()
            } catch (_: Exception) {
                Toast.makeText(this, "Could not download file", Toast.LENGTH_LONG).show()
            }
        }

        web.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                binding.progress.visibility = if (newProgress in 1..99) View.VISIBLE else View.GONE
                binding.progress.progress = newProgress
            }
        }

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?,
            ): Boolean {
                // Keep print pages and admin links inside the app.
                return false
            }

            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                binding.progress.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                binding.progress.visibility = View.GONE
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: android.webkit.WebResourceError?,
            ) {
                if (request?.isForMainFrame == true) {
                    Toast.makeText(
                        this@MainActivity,
                        getString(R.string.cannot_reach_site),
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }
        }

        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (binding.webView.canGoBack()) {
                        binding.webView.goBack()
                    } else {
                        finish()
                    }
                }
            },
        )

        if (Prefs.baseUrl(this).isEmpty()) {
            startActivity(Intent(this, SettingsActivity::class.java))
        } else {
            loadAdmin()
        }
    }

    override fun onResume() {
        super.onResume()
        if (Prefs.baseUrl(this).isNotEmpty() && binding.webView.url.isNullOrBlank()) {
            loadAdmin()
        }
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_refresh -> {
                binding.webView.reload()
                true
            }
            R.id.action_admin_home -> {
                loadAdmin()
                true
            }
            R.id.action_settings -> {
                startActivity(Intent(this, SettingsActivity::class.java))
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT < 33) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    private fun loadAdmin() {
        val url = Prefs.adminUrl(this)
        if (url.isEmpty()) {
            startActivity(Intent(this, SettingsActivity::class.java))
            return
        }
        binding.webView.loadUrl(url)
    }
}
