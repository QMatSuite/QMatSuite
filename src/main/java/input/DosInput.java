/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package input;


import com.consts.Constants.EnumNameList;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumSummation;
import com.consts.Constants.EnumUnitEnergy;
import com.programconst.DefaultFileNamesQE;

import agent.InputAgentDos;
import core.agent.WrapperInteger;
import core.com.consts.PhysicalConstants;
import core.com.error.InvalidKeyException;
import core.com.error.InvalidTypeException;
import core.com.error.ShowAlert;
import core.input.InputValueDouble;
import core.input.InputValueInt;
import core.input.InputValueString;
import javafx.scene.control.Alert.AlertType;


public class DosInput extends QeInput{
	
	public DosInput() {
		super("dos");
		sectionDict.put("DOS", new NameList(EnumNameList.DOS));
		sectionDict.get("DOS").setBoolRequired(true);
		sectionDict.get("DOS").addParameter("outdir", new InputValueString("outdir",DefaultFileNamesQE.outDir,true));//always write
		sectionDict.get("DOS").addParameter("Emax", new InputValueDouble("Emax",false));
		sectionDict.get("DOS").addParameter("Emin", new InputValueDouble("Emin",false));
		sectionDict.get("DOS").addParameter("DeltaE", new InputValueDouble("DeltaE",true));
		
		sectionDict.get("DOS").addParameter("bz_sum", new InputValueString("bz_sum",false));
		sectionDict.get("DOS").addParameter("ngauss", new InputValueInt("ngauss",0,false));
		sectionDict.get("DOS").addParameter("degauss", new InputValueDouble("degauss",false));
		
	}

	@Override
	public void loadAgent(InputAgentDos ia1) {
		try {
			final double mulFactor;
			if(ia1.energyUnit.equals(EnumUnitEnergy.Ry)) {mulFactor=PhysicalConstants.ryInEV;}
			else if(ia1.energyUnit.equals(EnumUnitEnergy.eV)) {mulFactor=1.0;}
			else {
				ShowAlert.showAlert(AlertType.ERROR, "Error", "Unidentified EnumUnitEnergy. Abort.");
				return;
	    	}
				
			//QE unit in eV
			andExplicitWrite("DOS","Emax",ia1.emax.isNull());
			if(!ia1.emax.isNull()) {setValue("DOS","Emax",ia1.emax,mulFactor);}
			
			andExplicitWrite("DOS","Emin",ia1.emin.isNull());
			if(!ia1.emin.isNull()) {setValue("DOS","Emin",ia1.emin,mulFactor);}
			
			if(!ia1.estep.isNull()) {setValue("DOS","DeltaE",ia1.estep,mulFactor);}
			
			boolean boolAdvanced = ia1.setAdvanced;
			
			andExplicitWrite("DOS","bz_sum",boolAdvanced);
			andExplicitWrite("DOS","ngauss",boolAdvanced);
			andExplicitWrite("DOS","degauss",boolAdvanced);
			
			if(boolAdvanced) {
				if(ia1.enumSummation.equals(EnumSummation.from_input)) {
					andExplicitWrite("DOS","bz_sum",false);
				}
				else {
					setValue("DOS","bz_sum",ia1.enumSummation);
				}
				final boolean boolWrite = ia1.enumSmearing.isEnabled();
				final int ngauss;
				switch((EnumSmearing)ia1.enumSmearing.getValue()) {
					case gauss:ngauss = 0;break;
					case fd:ngauss = -99;break;
					case mp:ngauss = 1;break;
					case mv:ngauss = -1;break;
					default:
						ShowAlert.showAlert(AlertType.ERROR, "Error", "Unidentified EnumSmearing. Abort");
						return;
				}
				setValue("DOS","ngauss",new WrapperInteger(ngauss,boolWrite));
				setValue("DOS","degauss",ia1.degauss,mulFactor/PhysicalConstants.ryInEV);//QE unit in Ry
			}
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			ShowAlert.showAlert(AlertType.ERROR, "Error", "Exception!"+e.getMessage());
		}
		
		
	}
	
}
