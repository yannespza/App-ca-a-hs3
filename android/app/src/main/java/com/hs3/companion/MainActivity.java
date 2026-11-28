package com.hs3.companion;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Abre o HS3 Companion do PC dentro de um app. Na primeira vez procura o PC na rede de casa. */
public class MainActivity extends Activity {
    private static final String INICIO = "file:///android_asset/inicio.html";
    private WebView web;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(Color.parseColor("#3a2316"));
        prefs = getSharedPreferences("hs3", MODE_PRIVATE);
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#3a2316"));
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setTextZoom(100);   // ignora a letra grande do sistema: o app já tem tamanhos próprios
        CookieManager.getInstance().setAcceptCookie(true);
        web.addJavascriptInterface(new Ponte(), "HS3");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                // o PC não respondeu (desligado, outro Wi-Fi, app fechado): volta para a tela de procurar
                if (req.isForMainFrame() && !req.getUrl().toString().startsWith("file:")) {
                    v.loadUrl(INICIO + "?erro=1");
                }
            }
        });
        String salvo = prefs.getString("url", "");
        web.loadUrl(salvo.isEmpty() ? INICIO : salvo);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    class Ponte {
        @JavascriptInterface
        public String ips() {
            List<String> l = new ArrayList<>();
            try {
                for (NetworkInterface n : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                    if (!n.isUp() || n.isLoopback()) continue;
                    for (InetAddress a : Collections.list(n.getInetAddresses())) {
                        if (a instanceof Inet4Address) l.add(a.getHostAddress());
                    }
                }
            } catch (Exception ignored) { }
            return String.join(",", l);
        }

        @JavascriptInterface
        public String salvo() { return prefs.getString("url", ""); }

        @JavascriptInterface
        public void abrir(final String url) {
            prefs.edit().putString("url", url).apply();
            runOnUiThread(() -> web.loadUrl(url));
        }

        @JavascriptInterface
        public void esquecer() {
            prefs.edit().remove("url").apply();
            runOnUiThread(() -> web.loadUrl(INICIO));
        }
    }
}
