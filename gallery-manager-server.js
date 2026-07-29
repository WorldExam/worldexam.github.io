const http = require("http");
const fs = require("fs/promises");
const path = require("path");

const PORT = Number(process.env.PORT || 4173);
const HOST = process.env.HOST || "127.0.0.1";
const ROOT = __dirname;
const GALLERY_DIR = path.join(ROOT, "gallery");
const UI_FILE = path.join(ROOT, "gallery-manager.html");
const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"]);

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
  });
  res.end(body);
}

function sendText(res, status, text, contentType = "text/plain; charset=utf-8") {
  res.writeHead(status, { "content-type": contentType });
  res.end(text);
}

function isImageFile(fileName) {
  return IMAGE_EXTENSIONS.has(path.extname(fileName).toLowerCase());
}

function assertSafeSegment(segment, label) {
  if (!segment || segment.includes("/") || segment.includes("\\") || segment === "." || segment === "..") {
    throw new Error(`Invalid ${label}`);
  }
  return segment;
}

function folderPath(folder) {
  const safeFolder = assertSafeSegment(folder, "folder");
  const resolved = path.resolve(GALLERY_DIR, safeFolder);
  if (!resolved.startsWith(path.resolve(GALLERY_DIR) + path.sep)) {
    throw new Error("Folder is outside gallery");
  }
  return resolved;
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  return raw ? JSON.parse(raw) : {};
}

async function listFolders() {
  const entries = await fs.readdir(GALLERY_DIR, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b));
}

async function listImages(folder) {
  const dir = folderPath(folder);
  const entries = await fs.readdir(dir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && isImageFile(entry.name))
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

async function handleApi(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/folders") {
    sendJson(res, 200, { folders: await listFolders() });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/images") {
    const folder = url.searchParams.get("folder") || "";
    const offset = Math.max(0, Number(url.searchParams.get("offset") || 0));
    const limit = Math.min(24, Math.max(1, Number(url.searchParams.get("limit") || 6)));
    const images = await listImages(folder);
    sendJson(res, 200, {
      folder,
      total: images.length,
      offset,
      limit,
      images: images.slice(offset, offset + limit),
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/image") {
    const folder = url.searchParams.get("folder") || "";
    const file = assertSafeSegment(url.searchParams.get("file") || "", "file");
    if (!isImageFile(file)) throw new Error("Unsupported file type");

    const imagePath = path.join(folderPath(folder), file);
    const data = await fs.readFile(imagePath);
    const extension = path.extname(file).toLowerCase().replace(".", "");
    const mime = extension === "jpg" ? "jpeg" : extension;
    res.writeHead(200, {
      "content-type": `image/${mime}`,
      "cache-control": "no-store",
    });
    res.end(data);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/delete") {
    const body = await readBody(req);
    const folder = body.folder || "";
    const files = Array.isArray(body.files) ? body.files : [];
    const dir = folderPath(folder);
    const deleted = [];

    for (const file of files) {
      const safeFile = assertSafeSegment(String(file), "file");
      if (!isImageFile(safeFile)) throw new Error(`Unsupported file type: ${safeFile}`);
      await fs.unlink(path.join(dir, safeFile));
      deleted.push(safeFile);
    }

    const remaining = await listImages(folder);
    sendJson(res, 200, { deleted, total: remaining.length });
    return;
  }

  sendJson(res, 404, { error: "Not found" });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname.startsWith("/api/")) {
      await handleApi(req, res, url);
      return;
    }

    if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/gallery-manager.html")) {
      const html = await fs.readFile(UI_FILE, "utf8");
      sendText(res, 200, html, "text/html; charset=utf-8");
      return;
    }

    sendText(res, 404, "Not found");
  } catch (error) {
    sendJson(res, 400, { error: error.message || "Request failed" });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Gallery manager running at http://${HOST}:${PORT}/gallery-manager.html`);
  console.log(`Gallery root: ${GALLERY_DIR}`);
});
