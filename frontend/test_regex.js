const text = `straight lines [Doc 4, Doc 48].
keep it as it is" [Doc 6, Doc 56].
enters [Doc 22].
answer [Source 3, 54].
[Source 1]
[1, 2]
[1]
[Document 5]
array [1,2,3]
[22, 62]`;

let displayContent = text;

displayContent = displayContent.replace(/\[((?:(?:Doc|Source|Document)s?\s*)?\d+(?:\s*,\s*(?:(?:Doc|Source|Document)s?\s*)?\d+)*)\]/gi, (match, inner) => {
  const ids = inner.match(/\d+/g);
  if (!ids) return match;
  return ids.map(id => `[${id}](#citation-${id})`).join(' ');
});

console.log(displayContent);
