package com.scratchcookiecottage.admin

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.scratchcookiecottage.admin.databinding.ActivitySettingsBinding
import java.net.URI

class SettingsActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        fitBelowSystemBars(binding.root)
        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        binding.toolbar.setNavigationOnClickListener { finish() }

        val existing = Prefs.baseUrl(this)
        binding.urlInput.setText(existing.ifEmpty { Prefs.DEFAULT_URL })
        binding.pushKeyInput.setText(Prefs.pushSecret(this).ifEmpty { Prefs.DEFAULT_PUSH_SECRET })

        binding.saveButton.setOnClickListener {
            val raw = binding.urlInput.text?.toString().orEmpty().trim()
            if (!isValidBaseUrl(raw)) {
                Toast.makeText(this, getString(R.string.invalid_url), Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            Prefs.setBaseUrl(this, raw)
            Prefs.setPushSecret(this, binding.pushKeyInput.text?.toString().orEmpty())
            PushRegistrar.register(this)
            Toast.makeText(this, getString(R.string.saved), Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    private fun isValidBaseUrl(value: String): Boolean {
        return try {
            val uri = URI(value)
            (uri.scheme == "http" || uri.scheme == "https") && !uri.host.isNullOrBlank()
        } catch (_: Exception) {
            false
        }
    }
}
