import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const routes = ["", "/how-it-works", "/pricing", "/docs", "/legal/privacy", "/legal/terms"];
  return routes.map((path) => ({
    url: `${site.url}${path}/`.replace(/\/+$/, "/"),
    lastModified: now,
    changeFrequency: path === "" ? "weekly" : "monthly",
    priority: path === "" ? 1.0 : 0.7,
  }));
}
