import fs from "node:fs/promises";
import path from "node:path";

const BASE_URL = process.env.MOBILE_BASE_URL || "http://127.0.0.1:5501";
const CDP_URL = process.env.CDP_URL || "http://127.0.0.1:9222";
const VEHICLE_ID = process.env.VEHICLE_ID || "1";
const BOOKING_ID = process.env.BOOKING_ID || "1";
const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR || "docs/mobile/screenshots";
const RESULT_PATH = process.env.RESULT_PATH || "docs/mobile/TF196F6-headless-results.json";

const PAGE_FILTER = process.env.PAGE_FILTER ? new Set(process.env.PAGE_FILTER.split(",")) : null;
const SIZE_FILTER = process.env.SIZE_FILTER ? new Set(process.env.SIZE_FILTER.split(",")) : null;

const SIZES = [
  { name: "360x740", width: 360, height: 740, mobile: true },
  { name: "390x844", width: 390, height: 844, mobile: true },
  { name: "414x896", width: 414, height: 896, mobile: true },
  { name: "768x1024", width: 768, height: 1024, mobile: false },
  { name: "1280x800", width: 1280, height: 800, mobile: false },
  { name: "844x390", width: 844, height: 390, mobile: true },
];

const PAGES = [
  { name: "vehicles", path: "/vehicles.html" },
  { name: "vehicle-detail", path: `/vehicle-detail.html?id=${VEHICLE_ID}` },
  { name: "booking", path: "/booking.html" },
  { name: "trips", path: "/trips.html" },
  { name: "payment-qr", path: `/payment-qr.html?booking_id=${BOOKING_ID}` },
  { name: "payment-result", path: `/payment-result.html?booking_id=${BOOKING_ID}` },
];

async function connectWebSocket(url) {
  const socket = new WebSocket(url);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = () => reject(new Error(`Không kết nối được CDP: ${url}`));
  });

  let nextId = 1;
  const pending = new Map();
  const events = [];

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const item = pending.get(message.id);
      if (!item) return;
      pending.delete(message.id);
      if (message.error) item.reject(new Error(message.error.message));
      else item.resolve(message.result);
      return;
    }
    if (message.method) events.push(message);
  };

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
  }

  return { socket, send, events };
}

async function waitForReady(client) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await client.send("Runtime.evaluate", {
      expression: "document.readyState",
      returnByValue: true,
    });
    if (response.result.value === "complete") break;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  await new Promise((resolve) => setTimeout(resolve, 1200));
}

function collectErrors(events) {
  const errors = [];
  for (const event of events) {
    if (event.method === "Runtime.exceptionThrown") {
      const detail = event.params?.exceptionDetails;
      errors.push(detail?.exception?.description || detail?.text || "Lỗi JavaScript");
    }
    if (
      event.method === "Log.entryAdded" &&
      event.params?.entry?.level === "error"
    ) {
      errors.push(
        `${event.params.entry.text}${event.params.entry.url ? ` ${event.params.entry.url}` : ""}`
      );
    }
  }
  return errors.slice(0, 10);
}

function collectNetworkErrors(events) {
  const errors = [];
  for (const event of events) {
    if (
      event.method === "Network.responseReceived" &&
      event.params?.response?.status >= 400
    ) {
      errors.push(`${event.params.response.status} ${event.params.response.url}`);
    }
    if (event.method === "Network.loadingFailed") {
      errors.push(`FAILED ${event.params?.errorText || ""}`);
    }
  }
  return errors.slice(0, 10);
}

const measureExpression = `(() => {
  const viewport = window.innerWidth;
  const offenders = [];
  const smallTargets = [];
  const clipped = [];
  const isHiddenByOpacity = (element) => {
    let node = element;
    while (node && node !== document.body) {
      if (getComputedStyle(node).opacity === "0") return true;
      node = node.parentElement;
    }
    return false;
  };

  const describe = (element, rect) => {
    const style = getComputedStyle(element);
    return {
    tag: element.tagName.toLowerCase(),
    id: element.id || "",
    className: typeof element.className === "string" ? element.className.slice(0, 90) : "",
    left: Math.round(rect.left),
    right: Math.round(rect.right),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    whiteSpace: style.whiteSpace,
    display: style.display,
    visibility: style.visibility,
    minHeight: style.minHeight,
    minWidth: style.minWidth,
    transform: style.transform,
    overflowX: style.overflowX,
    parentClass: typeof element.parentElement?.className === "string" ? element.parentElement.className.slice(0, 80) : "",
    ancestors: (() => {
      const list = [];
      let node = element.parentElement;
      for (let index = 0; node && index < 8; index += 1) {
        list.push(node.tagName.toLowerCase() + "." + (typeof node.className === "string" ? node.className.slice(0, 50) : ""));
        node = node.parentElement;
      }
      return list;
    })(),
    text: (element.textContent || "").trim().slice(0, 60)
    };
  };

  document.querySelectorAll("body *").forEach((element) => {
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const style = getComputedStyle(element);
    if (style.visibility === "hidden" || style.display === "none" || style.pointerEvents === "none" || isHiddenByOpacity(element)) return;
    if ((rect.right > viewport + 1 && rect.left < viewport - 1) || (rect.left < -1 && rect.right > 0)) {
      offenders.push(describe(element, rect));
    }
    if (
      element.scrollWidth > element.clientWidth + 2 &&
      !["auto", "scroll"].includes(style.overflowX)
    ) {
      clipped.push(describe(element, rect));
    }
  });

  document.querySelectorAll("button, a, input, select, [role=button]").forEach((element) => {
    if (["checkbox", "radio"].includes(element.type)) {
      const label = element.closest("label");
      if (label && label.getBoundingClientRect().height >= 44) return;
    }
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    if (!rect.width || !rect.height || style.visibility === "hidden" || style.display === "none" || isHiddenByOpacity(element)) return;
    if (rect.left < 0 || rect.right > viewport + 1) return;
    if (rect.height < 44 || rect.width < 44) {
      smallTargets.push({
        ...describe(element, rect),
        role: element.getAttribute("role") || "",
        disabled: element.disabled || false
      });
    }
  });

  return {
    innerWidth: viewport,
    scrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    offenderCount: offenders.length,
    offenders: offenders.slice(0, 10),
    smallTargetCount: smallTargets.length,
    smallTargets: smallTargets.slice(0, 14),
    clippedCount: clipped.length,
    clipped: clipped.slice(0, 10),
    title: document.title,
    interactiveCount: document.querySelectorAll("button, a, input, select, [role=button]").length
  };
})()`;

async function main() {
  await fs.mkdir(SCREENSHOT_DIR, { recursive: true });
  const targets = await fetch(`${CDP_URL}/json/list`).then((response) => response.json());
  const target = targets.find((item) => item.type === "page");
  if (!target) throw new Error("Chrome chưa có tab nào để đo.");

  const client = await connectWebSocket(target.webSocketDebuggerUrl);
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Log.enable");
  await client.send("Network.enable");
  await client.send("Network.setCacheDisabled", { cacheDisabled: true });
  const reduceMotionSource = [
    "(() => {",
    "  const style = document.createElement('style');",
    "  style.textContent = '*,*::before,*::after{animation:none!important;transition:none!important}[data-reveal]{opacity:1!important;transform:none!important}';",
    "  const attach = () => { const target = document.head || document.documentElement; if (target && !style.parentNode) target.appendChild(style); };",
    "  attach();",
    "  document.addEventListener('readystatechange', attach);",
    "})();",
  ].join("");
  await client.send("Page.addScriptToEvaluateOnNewDocument", { source: reduceMotionSource });

  const results = [];
  for (const size of SIZES.filter((item) => !SIZE_FILTER || SIZE_FILTER.has(item.name))) {
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: size.width,
      height: size.height,
      deviceScaleFactor: 1,
      mobile: size.mobile,
      screenWidth: size.width,
      screenHeight: size.height,
    });
    await client.send("Emulation.setTouchEmulationEnabled", {
      enabled: size.mobile,
      maxTouchPoints: size.mobile ? 5 : 1,
    });

    for (const page of PAGES.filter((item) => !PAGE_FILTER || PAGE_FILTER.has(item.name))) {
      client.events.length = 0;
      await client.send("Runtime.evaluate", {
        expression: "try { localStorage.clear(); } catch (error) {}",
      });
      const url = `${BASE_URL}${page.path}`;
      await client.send("Page.navigate", { url });
      await waitForReady(client);

      const measured = await client.send("Runtime.evaluate", {
        expression: measureExpression,
        returnByValue: true,
      });
      const metrics = measured.result.value;
      const errors = collectErrors(client.events);
      const networkErrors = collectNetworkErrors(client.events);
      const overflow = metrics.scrollWidth > metrics.innerWidth + 1;
      const screenshot = path.join(
        SCREENSHOT_DIR,
        `${page.name}-${size.name}.png`
      );
      const image = await client.send("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
      });
      await fs.writeFile(screenshot, Buffer.from(image.data, "base64"));

      const row = {
        page: page.name,
        size: size.name,
        innerWidth: metrics.innerWidth,
        scrollWidth: metrics.scrollWidth,
        bodyScrollWidth: metrics.bodyScrollWidth,
        overflow,
        offenderCount: metrics.offenderCount,
        offenders: metrics.offenders,
        smallTargetCount: metrics.smallTargetCount,
        smallTargets: metrics.smallTargets,
        clippedCount: metrics.clippedCount,
        clipped: metrics.clipped,
        interactiveCount: metrics.interactiveCount,
        errors,
        networkErrors,
        screenshot,
        url,
      };
      results.push(row);
      console.log(
        `${page.name.padEnd(15)} ${size.name.padEnd(8)} scroll=${metrics.scrollWidth}/${metrics.innerWidth} ` +
          `${overflow ? "TRÀN" : "OK"} offenders=${metrics.offenderCount} errors=${errors.length}`
      );
    }
  }

  await fs.writeFile(RESULT_PATH, JSON.stringify(results, null, 2) + "\n");
  console.log(`\nĐã ghi ${results.length} kết quả vào ${RESULT_PATH}`);
  const failed = results.filter((row) => row.overflow || row.errors.length);
  console.log(`Tràn ngang: ${results.filter((row) => row.overflow).length}; lỗi console: ${results.filter((row) => row.errors.length).length}`);
  client.socket.close();
  if (failed.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
