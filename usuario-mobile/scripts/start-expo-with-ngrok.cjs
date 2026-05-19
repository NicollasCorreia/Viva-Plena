/* global __dirname */
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const ngrok = require("@ngrok/ngrok");

const PORT = 8082;
const tunnelUrlFile = path.join(__dirname, "..", ".expo-tunnel-url.txt");

function withoutProxyEnv(sourceEnv) {
  const nextEnv = { ...sourceEnv };
  for (const key of [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
  ]) {
    delete nextEnv[key];
  }
  return nextEnv;
}

async function main() {
  const authtoken = process.env.NGROK_AUTHTOKEN;
  if (!authtoken) {
    throw new Error("NGROK_AUTHTOKEN nao encontrado no ambiente.");
  }

  const listener = await ngrok.forward({
    addr: PORT,
    authtoken,
    proto: "http",
    forwards_to: `localhost:${PORT}`,
  });

  const publicUrl = listener.url();
  fs.writeFileSync(tunnelUrlFile, `${publicUrl}\n`, "utf8");
  console.log(`Public tunnel ready at: ${publicUrl}`);
  console.log(`Saved public URL to: ${tunnelUrlFile}`);
  console.log(`Starting Expo with EXPO_PACKAGER_PROXY_URL=${publicUrl}`);

  const expoEnv = withoutProxyEnv(process.env);
  expoEnv.EXPO_PACKAGER_PROXY_URL = publicUrl;

  const expoProcess = process.platform === "win32"
    ? spawn(
        "cmd.exe",
        ["/d", "/s", "/c", `npx expo start --host lan --clear --port ${PORT}`],
        {
          stdio: "inherit",
          env: expoEnv,
          windowsHide: false,
        },
      )
    : spawn(
        "npx",
        ["expo", "start", "--host", "lan", "--clear", "--port", String(PORT)],
        {
          stdio: "inherit",
          env: expoEnv,
          windowsHide: false,
        },
      );

  const shutdown = async (signal) => {
    console.log(`\nShutting down tunnel (${signal})...`);
    try {
      expoProcess.kill("SIGINT");
    } catch (_) {
      // ignore
    }

    try {
      await listener.close();
    } catch (_) {
      // ignore
    }

    try {
      await ngrok.disconnect();
    } catch (_) {
      // ignore
    }

    try {
      if (fs.existsSync(tunnelUrlFile)) {
        fs.unlinkSync(tunnelUrlFile);
      }
    } catch (_) {
      // ignore
    }

    process.exit(0);
  };

  process.on("SIGINT", () => {
    shutdown("SIGINT");
  });

  process.on("SIGTERM", () => {
    shutdown("SIGTERM");
  });

  expoProcess.on("exit", async (code) => {
    try {
      await listener.close();
    } catch (_) {
      // ignore
    }
    try {
      if (fs.existsSync(tunnelUrlFile)) {
        fs.unlinkSync(tunnelUrlFile);
      }
    } catch (_) {
      // ignore
    }
    process.exit(code ?? 0);
  });
}

main().catch((error) => {
  console.error("Unable to start modern ngrok tunnel.");
  console.error(error && error.message ? error.message : error);
  process.exit(1);
});
