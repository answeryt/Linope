function introductionSummary(text: string) {
  const [summary] = text
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 0);
  return summary ?? "";
}

export { introductionSummary };
