import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1])
b.GetDesignSettings().SetAuxOrigin(pcbnew.VECTOR2I(pcbnew.FromMM(50), pcbnew.FromMM(50)))
b.GetDesignSettings().SetGridOrigin(pcbnew.VECTOR2I(pcbnew.FromMM(50), pcbnew.FromMM(50)))
pcbnew.SaveBoard(sys.argv[1], b)
print('aux origin set')
