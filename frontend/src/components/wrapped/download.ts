import { toPng } from "html-to-image";
import JSZip from "jszip";
import { CARD_HEIGHT, CARD_WIDTH } from "./cards";

/**
 * Renders an unscaled card node to a 1080×1920 PNG data URL.
 *
 * Waits for `document.fonts.ready` first: html-to-image embeds the web fonts it
 * finds, and a font still loading would fall back to the system monospace.
 * The dashboard already loads JetBrains Mono (@fontsource-variable/jetbrains-mono).
 */
async function renderCardPng(node: HTMLElement): Promise<string> {
  await document.fonts?.ready;
  return toPng(node, {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    pixelRatio: 1,
    backgroundColor: "#09090b", // zinc-950, so the PNG is never transparent
    cacheBust: true,
  });
}

function save(href: string, fileName: string): void {
  const link = document.createElement("a");
  link.href = href;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/** Saves one card as `fileName`. */
export async function downloadCard(node: HTMLElement, fileName: string): Promise<void> {
  save(await renderCardPng(node), fileName);
}

export interface CardExport {
  node: HTMLElement;
  fileName: string;
}

/** Saves every card as a PNG inside `zipName`, in order; nothing is saved if any card fails. */
export async function downloadAllCards(cards: CardExport[], zipName: string): Promise<void> {
  const zip = new JSZip();
  for (const { node, fileName } of cards) {
    const dataUrl = await renderCardPng(node);
    zip.file(fileName, dataUrl.slice(dataUrl.indexOf(",") + 1), { base64: true });
  }
  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  try {
    save(url, zipName);
  } finally {
    // Revoke after the click has handed the blob to the download.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
