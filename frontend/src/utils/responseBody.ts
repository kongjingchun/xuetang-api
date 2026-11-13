/**
 * @File    : responseBody.ts
 * @Desc    : 按响应头和正文自动选择展示格式与编码，并支持手动切换
 * @Author  : xuetang-api
 * @Date    : 2026-11-13
 */

export const BODY_FORMATS = ["预览", "JSON", "XML", "HTML", "Text"] as const;
export const BODY_ENCODINGS = ["UTF-8", "GBK", "GB2312", "ISO-8859-1"] as const;

const DECODER_LABEL: Record<(typeof BODY_ENCODINGS)[number], string> = {
  "UTF-8": "utf-8",
  GBK: "gbk",
  GB2312: "gb2312",
  "ISO-8859-1": "iso-8859-1",
};

/** 从响应头里取 Content-Type，不区分大小写。 */
export function contentTypeOf(headers: Record<string, string> | { name: string; value: string }[]): string {
  if (Array.isArray(headers)) {
    const found = headers.find((item) => item.name.toLowerCase() === "content-type");
    return found?.value || "";
  }
  const found = Object.entries(headers).find(([name]) => name.toLowerCase() === "content-type");
  return found?.[1] || "";
}

/** 把接口返回的 base64 原文还原成字节。 */
export function bytesFromBase64(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

/** 优先用响应头里的 charset，解码失败再试 UTF-8、GBK。 */
export function detectEncoding(bytes: Uint8Array, contentType: string): (typeof BODY_ENCODINGS)[number] {
  const charset = /charset="?([^";]+)/i.exec(contentType)?.[1]?.trim().toLowerCase() || "";
  if (charset.includes("gb2312")) {
    return "GB2312";
  }
  if (charset.includes("gbk") || charset.includes("gb18030")) {
    return "GBK";
  }
  if (charset.includes("8859-1") || charset.includes("latin1")) {
    return "ISO-8859-1";
  }
  if (charset.includes("utf-8") || charset.includes("utf8")) {
    return "UTF-8";
  }
  if (canDecode(bytes, "utf-8")) {
    return "UTF-8";
  }
  if (canDecode(bytes, "gbk")) {
    return "GBK";
  }
  return "ISO-8859-1";
}

export interface PreviewNode {
  id: string;
  label: string;
  kind: "object" | "array" | "element" | "string" | "number" | "boolean" | "null";
  value: string;
  children: PreviewNode[];
}

let previewSeq = 0;

/** 能展开成树的 JSON 或 XML 返回节点，否则返回空。 */
export function parsePreview(text: string): PreviewNode | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.startsWith("{") || trimmed.startsWith("[") || trimmed.startsWith('"') || /^-?\d/.test(trimmed) || trimmed === "true" || trimmed === "false" || trimmed === "null") {
    try {
      return fromJson(JSON.parse(trimmed), "");
    } catch {
      // 不是 JSON 时继续尝试 XML。
    }
  }
  if (trimmed.startsWith("<")) {
    const doc = new DOMParser().parseFromString(trimmed, "application/xml");
    if (!doc.querySelector("parsererror") && doc.documentElement) {
      return fromElement(doc.documentElement);
    }
  }
  return null;
}

/** 能按层级预览时默认预览，否则按媒体类型选择文本格式。 */
export function detectFormat(text: string, contentType: string): (typeof BODY_FORMATS)[number] {
  const trimmed = text.trim();
  const media = contentType.toLowerCase();
  if (parsePreview(trimmed)) {
    return "预览";
  }
  if (media.includes("json") || looksLikeJson(trimmed)) {
    return "JSON";
  }
  if (media.includes("html") || /^<!doctype html/i.test(trimmed) || /^<html[\s>]/i.test(trimmed)) {
    return "HTML";
  }
  if (media.includes("xml") || trimmed.startsWith("<?xml") || (trimmed.startsWith("<") && trimmed.endsWith(">"))) {
    return "XML";
  }
  return "Text";
}

/** 用选定编码解出文本，再按选定格式排版。解不开时退回 UTF-8。 */
export function presentBody(base64: string, encoding: string, format: string): string {
  if (!base64) {
    return "";
  }
  const bytes = bytesFromBase64(base64);
  const label = DECODER_LABEL[encoding as (typeof BODY_ENCODINGS)[number]] || "utf-8";
  let text = "";
  try {
    text = new TextDecoder(label).decode(bytes);
  } catch {
    text = new TextDecoder("utf-8").decode(bytes);
  }
  if (format === "JSON") {
    return prettyJson(text);
  }
  if (format === "XML" || format === "HTML") {
    return prettyMarkup(text);
  }
  return text;
}

function canDecode(bytes: Uint8Array, label: string): boolean {
  try {
    new TextDecoder(label, { fatal: true }).decode(bytes);
    return true;
  } catch {
    return false;
  }
}

function fromJson(value: unknown, label: string): PreviewNode {
  previewSeq += 1;
  const id = `n${previewSeq}`;
  if (Array.isArray(value)) {
    return { id, label, kind: "array", value: String(value.length), children: value.map((item, index) => fromJson(item, String(index))) };
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return { id, label, kind: "object", value: String(entries.length), children: entries.map(([key, item]) => fromJson(item, key)) };
  }
  if (typeof value === "string") {
    return { id, label, kind: "string", value, children: [] };
  }
  if (typeof value === "number") {
    return { id, label, kind: "number", value: String(value), children: [] };
  }
  if (typeof value === "boolean") {
    return { id, label, kind: "boolean", value: String(value), children: [] };
  }
  return { id, label, kind: "null", value: "null", children: [] };
}

function fromElement(element: Element): PreviewNode {
  previewSeq += 1;
  const text = [...element.childNodes].every((item) => item.nodeType !== Node.ELEMENT_NODE) ? (element.textContent || "").trim() : "";
  const attrs = [...element.attributes].map((item) => `${item.name}="${item.value}"`).join(" ");
  return {
    id: `n${previewSeq}`,
    label: element.tagName,
    kind: "element",
    value: text || attrs,
    children: [...element.children].map((item) => fromElement(item)),
  };
}

function looksLikeJson(text: string): boolean {
  if (!text.startsWith("{") && !text.startsWith("[")) {
    return false;
  }
  try {
    JSON.parse(text);
    return true;
  } catch {
    return false;
  }
}

function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function prettyMarkup(text: string): string {
  const compact = text.replace(/>\s+</g, "><").trim();
  if (!compact.startsWith("<")) {
    return text;
  }
  const tokens = compact.match(/<\/?[^>]+>|[^<]+/g) || [];
  let pad = 0;
  return tokens
    .map((token) => {
      const piece = token.trim();
      if (!piece) {
        return "";
      }
      if (piece.startsWith("</")) {
        pad = Math.max(pad - 1, 0);
        return `${"  ".repeat(pad)}${piece}`;
      }
      const line = `${"  ".repeat(pad)}${piece}`;
      if (piece.startsWith("<") && !piece.endsWith("/>") && !piece.startsWith("<?") && !piece.startsWith("<!")) {
        pad += 1;
      }
      return line;
    })
    .filter(Boolean)
    .join("\n");
}
