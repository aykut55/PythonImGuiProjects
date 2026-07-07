# Hazir: gm, pm, dpg, Panel, PanelData

def main():
    dpg.configure_item("centerTopPanel", show=False)
    
    pm.setContainer("centerCenterPanel")
    
    pm.deleteAllPanels()

    ohlcPanel = pm.createPanel("OHLC", "OHLC Verisi")
    ohlcPanel.setHeight(400)
    pm.addPanel(ohlcPanel)

    movAvgPanel = pm.createPanel("MovAvg", "Hareketli Ortalamalar")
    movAvgPanel.setHeight(300)
    pm.addPanel(movAvgPanel)

    macdPanel = pm.createPanel("MACD", "MACD")
    macdPanel.setHeight(200)
    pm.addPanel(macdPanel)

    rsiPanel = pm.createPanel("RSI", "RSI")
    rsiPanel.setHeight(200)
    pm.addPanel(rsiPanel)

    stochPanel = pm.createPanel("Stochastic", "Stochastic %K / %D")
    stochPanel.setHeight(200)
    pm.addPanel(stochPanel)

    # Y ekseni senkron gruplari
    ohlcPanel.setYSyncId(0)
    movAvgPanel.setYSyncId(0)
    macdPanel.setYSyncId(1)
    rsiPanel.setYSyncId(2)
    stochPanel.setYSyncId(3)

    # pm.drawPanels()
    for p in pm.iterateAllPanels():
        pm.drawPanel(p.id)

    # getPanelId ornegi: referans (ohlcPanel) elde olmasa bile isimle id bulunur.
    ohlcId = pm.getPanelId("OHLC")
    print(f"OHLC panelinin id'si: {ohlcId}")

    print("Paneller olusturuldu:")
    
    for p in pm.getAllPanels():
        print(f"  id={p.id}  name={p.name}  height={p.height}")

    for p in pm.iterateAllPanels():
        print(f"  id={p.id}  name={p.name}  height={p.height}")

    print("Bitti.")


main()
