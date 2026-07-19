from pathlib import Path
NOTICE="Synthetic portfolio demonstration data — not a real company record."
root=Path(__file__).parents[1]/'data'/'synthetic_documents';root.mkdir(parents=True,exist_ok=True)
for name,title in [('engineering-change-order.md','Engineering Change Order'),('supplier-package-change.md','Supplier Packaging Change Notice'),('release-approval-memo.md','Release Approval Memo')]:
    (root/name).write_text(f'# {title}\n\n**{NOTICE}**\n\nNorthstar Industrial Systems synthetic demonstration document.\n',encoding='utf-8')
