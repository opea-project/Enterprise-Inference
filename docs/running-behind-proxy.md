# Running behind a corporate proxy

If you are working in a corporate environment where internet access is routed through a proxy, you need to configure the appropriate proxy settings for tools and scripts to work correctly.

This is supported using proxy configuration through inference-config.cfg file

---

## Configuration Steps

1. Open the configuration file:

   ```bash
   inference-config.cfg
   ```

2. Add the following three environment variables with your proxy details:

   ```bash
   http_proxy="http://your.proxy.server:port"
   https_proxy="http://your.proxy.server:port"
   no_proxy="localhost,127.0.0.1,example.local"
   ```

   > **Note:** Make sure to include any internal domains or IPs in `no_proxy` that should bypass the proxy.

---

## Example

```ini
http_proxy="http://proxy.corporate.com:8080"
https_proxy="http://proxy.corporate.com:8080"
no_proxy="localhost,127.0.0.1,.mycompany.com"
```

To unset proxy from apt, please remove proxy configurations from below file
sudo nano  /etc/apt/apt.conf
