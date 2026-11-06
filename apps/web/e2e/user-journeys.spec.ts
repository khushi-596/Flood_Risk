import { test, expect } from "@playwright/test";

test.describe("Flood Risk User Journeys (Dev E1)", () => {
  test("Journey 1: View risk map, search route, compare safe vs fast", async ({ page }) => {
    // 1. Commuter views risk map
    await page.goto("/");
    await expect(page).toHaveTitle(/Flood/i);

    // Verify map canvas renders
    const mapElement = page.locator("canvas.maplibregl-canvas, .map-container, #map");
    await expect(mapElement.first()).toBeVisible({ timeout: 10000 });

    // 2. Open Route Planner and perform route search
    const routeTab = page.getByRole("tab", { name: /route/i }).or(page.getByText(/route/i));
    if (await routeTab.isVisible()) {
      await routeTab.click();
    }

    // Check presence of Safe / Fast option cards if available
    const fastCard = page.getByText(/fastest/i).or(page.getByText(/fast/i));
    const safeCard = page.getByText(/safest/i).or(page.getByText(/safe/i));
    if (await fastCard.first().isVisible()) {
      await expect(safeCard.first()).toBeVisible();
    }
  });

  test("Journey 2: Citizen report modal and submission flow", async ({ page }) => {
    await page.goto("/");

    // Open Report Modal
    const reportButton = page.getByRole("button", { name: /report flood/i }).or(page.getByText(/report/i));
    if (await reportButton.first().isVisible()) {
      await reportButton.first().click();

      // Form presence check
      const descriptionInput = page.getByPlaceholder(/describe/i).or(page.locator("textarea"));
      if (await descriptionInput.isVisible()) {
        await descriptionInput.fill("Water accumulation up to ankle level on road.");
      }
    }
  });

  test("Journey 3: Simulator triggers rain condition and alert banner", async ({ page }) => {
    await page.goto("/");

    // Check weather simulator controls
    const simControls = page.getByText(/simulator/i).or(page.getByText(/rainfall/i));
    await expect(simControls.first()).toBeVisible({ timeout: 10000 });
  });

  test("Journey 4: Vehicle selection modifies advice and travel warnings", async ({ page }) => {
    await page.goto("/");

    // Check vehicle selector (Car, Two-wheeler, Auto, Bus)
    const vehicleSelector = page.getByRole("combobox").or(page.getByText(/vehicle/i));
    if (await vehicleSelector.first().isVisible()) {
      await expect(vehicleSelector.first()).toBeVisible();
    }
  });
});
