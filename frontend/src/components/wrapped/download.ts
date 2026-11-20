import { toPng } from "html-to-image";
import { CARD_HEIGHT, CARD_WIDTH } from "./cards";

/**
 * Renders the unscaled card node to a 1080×1920 PNG and saves it.
 *
 * Waits for `document.fonts.ready` first: html-to-image embeds the web fonts it
 * finds, and a font still loading would fall back to the system monospace.
 * The dashboard already loads JetBrains Mono (@fontsource-variable/jetbrains-mono).
 */
export async function downloadCard(node: HTMLElement, fileName: string): Promise<void> {
  await document.fonts?.ready;
  const dataUrl = await toPng(node, {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    pixelRatio: 1,
    backgroundColor: "#09090b", // zinc-950, so the PNG is never transparent
    cacheBust: true,
  });
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
}
