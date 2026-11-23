import { glassDoc } from "@/docs/components/glass";
import { glassButtonDoc } from "@/docs/components/glass-button";
import { glassDialogDoc } from "@/docs/components/glass-dialog";
import { glassDockDoc } from "@/docs/components/glass-dock";
import { glassInputDoc } from "@/docs/components/glass-input";
import { glassPopoverDoc } from "@/docs/components/glass-popover";
import { glassSliderDoc } from "@/docs/components/glass-slider";
import { glassSwitchDoc } from "@/docs/components/glass-switch";
import { glassTabsDoc } from "@/docs/components/glass-tabs";
import { glassTooltipDoc } from "@/docs/components/glass-tooltip";
import type { ComponentDoc } from "@/docs/types";

const DOCS: ComponentDoc[] = [
  glassDoc,
  glassButtonDoc,
  glassDialogDoc,
  glassDockDoc,
  glassInputDoc,
  glassPopoverDoc,
  glassSliderDoc,
  glassSwitchDoc,
  glassTabsDoc,
  glassTooltipDoc,
];

const docBySlug = new Map(DOCS.map((doc) => [doc.slug, doc]));

export { DOCS, docBySlug };
