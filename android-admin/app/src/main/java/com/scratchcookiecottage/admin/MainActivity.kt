package com.scratchcookiecottage.admin

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.scratchcookiecottage.admin.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)

        val web = binding.webView
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)

        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.builtInZoomControls = true
        web.settings.displayZoomControls = false
        web.settings.loadWithOverviewMode = true
        web.settings.useWideViewPort = true

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

    private fun loadAdmin() {
        val url = Prefs.adminUrl(this)
        if (url.isEmpty()) {
            startActivity(Intent(this, SettingsActivity::class.java))
            return
        }
        binding.webView.loadUrl(url)
    }
}
