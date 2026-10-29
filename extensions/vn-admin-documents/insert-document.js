// Editor-side command for vn-admin-documents. `callCommand` serialises this
// function and runs it inside the Writer with the Office JS `Api`, so it must
// be self-contained: no imports, no closures; inputs arrive via `Asc.scope`:
//   Asc.scope.layout        – { blocks } from logic/nd30-layout.js
//   Asc.scope.pageSetup     – null or { marginsMm: {top,bottom,left,right}, pageMm: {width,height} }
//   Asc.scope.fontFamily    – font family name
// Returns { inserted, pageSetupApplied } on success or { error, stage, modified } on
// failure (callCommand would otherwise report success for a thrown error).
// Content is inserted before page setup so a failure leaves page size intact.

export function insertLayoutCommand() {
  let stage = 'prepare';
  try {
  const scope = Asc.scope;
  const MM_TO_TWIPS = 56.6929;
  const twips = (mm) => Math.round(mm * MM_TO_TWIPS);
  const doc = Api.GetDocument();
  const setup = scope.pageSetup;
  const margins = setup ? setup.marginsMm : null;
  const textWidthMm = setup ? setup.pageMm.width - margins.left - margins.right : 165;

  const ALIGN = { left: 'left', right: 'right', center: 'center', justify: 'both' };

  function makeParagraph(block) {
    const p = Api.CreateParagraph();
    p.SetJc(ALIGN[block.align] || 'left');
    p.SetSpacingBefore(Math.round((block.spacingBeforePt || 0) * 20));
    p.SetSpacingAfter(Math.round((block.spacingAfterPt || 0) * 20));
    p.SetSpacingLine(Math.round(240 * (block.lineSpacing || 1)), 'auto');
    if (block.indentFirstMm) p.SetIndFirstLine(twips(block.indentFirstMm));
    block.runs.forEach((spec) => {
      const r = Api.CreateRun();
      r.AddText(spec.text);
      r.SetFontFamily(scope.fontFamily);
      r.SetFontSize(Math.round(spec.size * 2));
      r.SetBold(!!spec.bold);
      r.SetItalic(!!spec.italic);
      r.SetLanguage('vi-VN');
      p.AddElement(r);
    });
    return p;
  }

  // Short centred horizontal rule: an empty paragraph with a bottom border
  // whose width is controlled by symmetric indents inside the given width.
  function makeRule(widthMm, containerMm) {
    const p = Api.CreateParagraph();
    const side = Math.max(0, (containerMm - widthMm) / 2);
    p.SetIndLeft(twips(side));
    p.SetIndRight(twips(side));
    p.SetSpacingAfter(0);
    p.SetSpacingLine(40, 'exact');
    p.SetBottomBorder('single', 6, 0, 0, 0, 0);
    return p;
  }

  function pushBlock(target, block, containerMm) {
    target.push(makeParagraph(block));
    if (block.ruleWidthMm) target.push(makeRule(block.ruleWidthMm, containerMm));
  }

  function makeTable(block) {
    // Verified on Desktop 10.0.0.169: CreateTable(a, b) yields a rows x b cells.
    const table = Api.CreateTable(1, 2);
    // Fixed twip widths: percentage widths only settle after a later relayout.
    table.SetWidth('twips', twips(textWidthMm));
    table.SetTableLayout('fixed');
    ['Top', 'Bottom', 'Left', 'Right', 'InsideH', 'InsideV'].forEach((edge) => {
      table['SetTableBorder' + edge]('none', 0, 0, 0, 0, 0);
    });
    [block.left, block.right].forEach((items, index) => {
      const cell = table.GetRow(0).GetCell(index);
      cell.SetWidth('twips', twips((textWidthMm * block.widthsPct[index]) / 100));
      const content = cell.GetContent();
      content.RemoveAllElements();
      const widthMm = (textWidthMm * block.widthsPct[index]) / 100;
      const elements = [];
      items.forEach((item) => pushBlock(elements, item, widthMm));
      elements.forEach((el) => content.Push(el));
      // RemoveAllElements keeps one empty paragraph; drop it so cells start with content.
      if (content.GetElementsCount() > elements.length) content.RemoveElement(0);
    });
    return table;
  }

  stage = 'build';
  const elements = [];
  scope.layout.blocks.forEach((block) => {
    if (block.type === 'two-column') {
      if (block.spacingBeforePt) elements.push(makeParagraph({ runs: [], spacingAfterPt: block.spacingBeforePt }));
      elements.push(makeTable(block));
    } else {
      pushBlock(elements, block, textWidthMm);
    }
  });
  stage = 'insert';
  doc.InsertContent(elements);
  if (setup) {
    stage = 'page-setup';
    const section = doc.GetFinalSection();
    section.SetPageSize(twips(setup.pageMm.width), twips(setup.pageMm.height));
    section.SetPageMargins(twips(margins.left), twips(margins.top), twips(margins.right), twips(margins.bottom));
  }
  return { inserted: elements.length, pageSetupApplied: !!setup };
  } catch (error) {
    const modified = stage === 'insert' || stage === 'page-setup';
    return { error: String((error && error.message) || error), stage, modified };
  }
}
