/**
 * @File    : curl.ts
 * @Desc    : 把粘贴的 curl 命令拆成方法、地址、请求头、Query、REST 和请求体
 * @Author  : xuetang-api
 * @Date    : 2026-11-13
 * @Update  : 2026-11-13 初始化 curl 解析
 */

export interface CurlParam {
  name: string;
  value: string;
  description: string;
  enabled: boolean;
}

export interface CurlRequest {
  method: string;
  url: string;
  headers: CurlParam[];
  query: CurlParam[];
  rest: CurlParam[];
  bodyType: string;
  bodyText: string;
}

const VALUE_FLAGS = new Set([
  "-X",
  "--request",
  "-H",
  "--header",
  "-d",
  "--data",
  "--data-raw",
  "--data-binary",
  "--data-ascii",
  "--data-urlencode",
  "-u",
  "--user",
  "-A",
  "--user-agent",
  "-e",
  "--referer",
  "-b",
  "--cookie",
  "--url",
]);

/** 按引号切分 curl，并去掉换行续行符。 */
function tokenize(input: string): string[] {
  const text = input.replace(/\\\r?\n/g, " ").replace(/\^\r?\n/g, " ").trim();
  const tokens: string[] = [];
  let current = "";
  let quote: "'" | '"' | null = null;
  for (const ch of text) {
    if (quote) {
      if (ch === quote) {
        quote = null;
      } else {
        current += ch;
      }
      continue;
    }
    if (ch === "'" || ch === '"') {
      quote = ch;
      continue;
    }
    if (/\s/.test(ch)) {
      if (current) {
        tokens.push(current);
        current = "";
      }
      continue;
    }
    current += ch;
  }
  if (current) {
    tokens.push(current);
  }
  return tokens;
}

function param(name: string, value: string): CurlParam {
  return { name, value, description: "", enabled: true };
}

function splitQuery(raw: string): { url: string; query: CurlParam[] } {
  const hash = raw.indexOf("#");
  const withoutHash = hash >= 0 ? raw.slice(0, hash) : raw;
  const mark = withoutHash.indexOf("?");
  if (mark < 0) {
    return { url: withoutHash, query: [] };
  }
  const query: CurlParam[] = [];
  for (const part of withoutHash.slice(mark + 1).split("&")) {
    if (!part) {
      continue;
    }
    const eq = part.indexOf("=");
    const name = decodeURIComponent(eq < 0 ? part : part.slice(0, eq));
    const value = decodeURIComponent(eq < 0 ? "" : part.slice(eq + 1).replace(/\+/g, " "));
    query.push(param(name, value));
  }
  return { url: withoutHash.slice(0, mark), query };
}

function restFromUrl(url: string): CurlParam[] {
  const path = url.replace(/^https?:\/\/[^/]+/i, "");
  const rows: CurlParam[] = [];
  for (const match of path.matchAll(/\{([^{}]+)\}/g)) {
    rows.push(param(match[1], ""));
  }
  return rows;
}

function flagName(token: string): { name: string; inline: string } {
  const eq = token.indexOf("=");
  if (token.startsWith("--") && eq > 0) {
    return { name: token.slice(0, eq), inline: token.slice(eq + 1) };
  }
  return { name: token, inline: "" };
}

/** 识别 curl 命令。不是 curl 时返回 null。 */
export function parseCurl(input: string): CurlRequest | null {
  const tokens = tokenize(input);
  if (!tokens.length || tokens[0].toLowerCase() !== "curl") {
    return null;
  }
  let method = "";
  let rawUrl = "";
  let forceGet = false;
  const headers: CurlParam[] = [];
  const query: CurlParam[] = [];
  const bodyParts: string[] = [];
  const queryFromData: string[] = [];
  for (let index = 1; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token === "-G" || token === "--get") {
      forceGet = true;
      continue;
    }
    if (token.startsWith("-X") && token.length > 2 && !token.startsWith("--")) {
      method = token.slice(2).toUpperCase();
      continue;
    }
    const flag = flagName(token);
    const takesValue = VALUE_FLAGS.has(flag.name);
    const value = flag.inline || (takesValue ? tokens[++index] || "" : "");
    if (flag.name === "-X" || flag.name === "--request") {
      method = value.toUpperCase();
    } else if (flag.name === "-H" || flag.name === "--header") {
      const splitAt = value.indexOf(":");
      if (splitAt > 0) {
        headers.push(param(value.slice(0, splitAt).trim(), value.slice(splitAt + 1).trim()));
      }
    } else if (flag.name === "-b" || flag.name === "--cookie") {
      headers.push(param("Cookie", value));
    } else if (flag.name === "-A" || flag.name === "--user-agent") {
      headers.push(param("User-Agent", value));
    } else if (flag.name === "-e" || flag.name === "--referer") {
      headers.push(param("Referer", value));
    } else if (flag.name === "-u" || flag.name === "--user") {
      headers.push(param("Authorization", `Basic ${btoa(value)}`));
    } else if (flag.name === "--url") {
      rawUrl = value;
    } else if (flag.name === "--data-urlencode") {
      queryFromData.push(value);
    } else if (flag.name === "-d" || flag.name.startsWith("--data")) {
      bodyParts.push(value);
    } else if (!token.startsWith("-") && !rawUrl) {
      rawUrl = token;
    }
  }
  if (!rawUrl) {
    return null;
  }
  const split = splitQuery(rawUrl);
  if (forceGet) {
    for (const item of bodyParts) {
      queryFromData.push(item);
    }
    bodyParts.length = 0;
  }
  for (const item of queryFromData) {
    const eq = item.indexOf("=");
    split.query.push(param(eq < 0 ? item : item.slice(0, eq), eq < 0 ? "" : item.slice(eq + 1)));
  }
  const contentType = headers.find((item) => item.name.toLowerCase() === "content-type")?.value.toLowerCase() || "";
  const bodyText = bodyParts.join("&");
  let bodyType = "none";
  if (bodyText) {
    if (contentType.includes("json")) {
      bodyType = "json";
    } else if (contentType.includes("x-www-form-urlencoded")) {
      bodyType = "x-www-form-urlencoded";
    } else if (contentType.includes("xml")) {
      bodyType = "xml";
    } else {
      bodyType = "raw";
    }
  }
  return {
    method: method || (bodyText ? "POST" : "GET"),
    url: split.url,
    headers,
    query: split.query,
    rest: restFromUrl(split.url),
    bodyType,
    bodyText,
  };
}
