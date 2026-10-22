"use strict";
const searchBox = document.getElementById("search");
const searchStatus = document.getElementById("search-status");
searchBox.addEventListener("input", () => {
  const query = searchBox.value.trim().toLocaleLowerCase();
  const rows = Array.from(document.querySelectorAll("tr.searchable"));
  let visible = 0;
  rows.forEach(row => {
    row.hidden = Boolean(query) && !row.textContent.toLocaleLowerCase().includes(query);
    if (!row.hidden) visible += 1;
  });
  searchStatus.textContent = query ? `显示 ${visible} / ${rows.length} 条登记记录` : "";
});
