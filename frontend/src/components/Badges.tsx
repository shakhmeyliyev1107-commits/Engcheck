import { type Key, useI18n } from "../i18n";

const SEVERITY_MARK: Record<string, string> = { critical: "▲", major: "◆", minor: "●", info: "○" };

// Jiddiylik faqat rang bilan emas, belgi va matn bilan ham ko'rsatiladi.
export function SeverityBadge({ value }: { value: string }) {
  const { t } = useI18n();
  return (
    <span className={`badge sev-${value}`}>
      <span aria-hidden="true">{SEVERITY_MARK[value] ?? "○"}</span> {t(`severity.${value}` as Key)}
    </span>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const { t } = useI18n();
  return <span className={`badge st-${value}`} data-testid="status-badge">{t(`status.${value}` as Key)}</span>;
}

export function ParseBadge({ value }: { value: string }) {
  const { t } = useI18n();
  return <span className={`badge parse-${value}`}>{t(`parse.${value}` as Key)}</span>;
}
