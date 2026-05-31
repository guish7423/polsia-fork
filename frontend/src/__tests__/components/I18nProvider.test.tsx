import "@testing-library/jest-dom";
import { render, screen, act, renderHook } from "@testing-library/react";
import { I18nProvider, useI18n, type Locale } from "@/lib/i18n";

// Helper to render with provider
function renderWithProvider(ui: React.ReactElement, locale?: Locale) {
  // Simulate initial locale via localStorage
  if (locale) {
    localStorage.setItem("polsia-locale", locale);
  }
  return render(<I18nProvider>{ui}</I18nProvider>);
}

describe("I18nProvider", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("provides English translations by default", () => {
    function TestComp() {
      const { t } = useI18n();
      return <div>{t("nav.dashboard")}</div>;
    }
    renderWithProvider(<TestComp />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("provides Chinese translations when locale is zh", () => {
    function TestComp() {
      const { t } = useI18n();
      return <div>{t("nav.dashboard")}</div>;
    }
    renderWithProvider(<TestComp />, "zh");
    expect(screen.getByText("仪表盘")).toBeInTheDocument();
  });

  it("falls back to English key when key not in Chinese", () => {
    function TestComp() {
      const { t } = useI18n();
      return <div>{t("nonexistent.key")}</div>;
    }
    renderWithProvider(<TestComp />, "zh");
    expect(screen.getByText("nonexistent.key")).toBeInTheDocument();
  });

  it("switches locale via setLocale", () => {
    function TestComp() {
      const { t, setLocale } = useI18n();
      return (
        <div>
          <span data-testid="text">{t("nav.dashboard")}</span>
          <button onClick={() => setLocale("zh")}>Switch</button>
        </div>
      );
    }
    renderWithProvider(<TestComp />);

    expect(screen.getByTestId("text")).toHaveTextContent("Dashboard");

    act(() => {
      screen.getByText("Switch").click();
    });

    expect(screen.getByTestId("text")).toHaveTextContent("仪表盘");
  });

  it("persists locale to localStorage", () => {
    function TestComp() {
      const { setLocale } = useI18n();
      return <button onClick={() => setLocale("zh")}>Switch</button>;
    }
    renderWithProvider(<TestComp />);

    act(() => {
      screen.getByText("Switch").click();
    });

    expect(localStorage.getItem("polsia-locale")).toBe("zh");
  });

  it("restores locale from localStorage on mount", () => {
    localStorage.setItem("polsia-locale", "zh");

    function TestComp() {
      const { locale } = useI18n();
      return <div data-testid="locale">{locale}</div>;
    }
    renderWithProvider(<TestComp />);

    expect(screen.getByTestId("locale")).toHaveTextContent("zh");
  });
});

describe("useI18n hook", () => {
  it("throws error when used outside provider", () => {
    // useI18n should still work with default context (no error)
    const { result } = renderHook(() => useI18n());
    // Default t returns the key itself
    expect(result.current.t("some.key")).toBe("some.key");
  });
});
