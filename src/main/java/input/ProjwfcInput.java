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
import com.consts.Constants.EnumUnitEnergy;
import com.programconst.DefaultFileNamesQE;

import agent.InputAgentBands;
import agent.InputAgentDos;
import core.agent.WrapperBoolean;
import core.agent.WrapperInteger;
import core.com.consts.PhysicalConstants;
import core.com.error.InvalidKeyException;
import core.com.error.InvalidTypeException;
import core.com.error.ShowAlert;
import core.input.InputValueBoolean;
import core.input.InputValueDouble;
import core.input.InputValueInt;
import core.input.InputValueString;
import javafx.scene.control.Alert.AlertType;


public class ProjwfcInput extends QeInput{
	
	public ProjwfcInput() {
		super("projwfc");
		sectionDict.put("projwfc", new NameList(EnumNameList.PROJWFC));
		sectionDict.get("projwfc").setBoolRequired(true);
		sectionDict.get("projwfc").addParameter("outdir", new InputValueString("outdir",DefaultFileNamesQE.outDir,true));//always write
		
		//for PDOS
		sectionDict.get("projwfc").addParameter("Emax", new InputValueDouble("Emax",false));//yes
		sectionDict.get("projwfc").addParameter("Emin", new InputValueDouble("Emin",false));//yes
		sectionDict.get("projwfc").addParameter("DeltaE", new InputValueDouble("DeltaE",false));//yes
		
		sectionDict.get("projwfc").addParameter("ngauss", new InputValueInt("ngauss",0,false));//yes
		sectionDict.get("projwfc").addParameter("degauss", new InputValueDouble("degauss",0.0,false));//yes
		
		sectionDict.get("projwfc").addParameter("lwrite_overlaps", new InputValueBoolean("lwrite_overlaps",false,false));
		sectionDict.get("projwfc").addParameter("filpdos", new InputValueString("filpdos",DefaultFileNamesQE.filpdos,false));
		
		//for projected bands
		sectionDict.get("projwfc").addParameter("filproj", new InputValueString("filproj",DefaultFileNamesQE.filproj,false));
		sectionDict.get("projwfc").addParameter("lsym", new InputValueBoolean("lsym",true,false));
	}
	@Override
	public void loadAgent(InputAgentBands ia1) {
		try {
			setRequiredAndWrite("projwfc","filproj",true,true);
			setValue("projwfc","lsym",new WrapperBoolean(false,true));
			setRequiredAndWrite("projwfc","lsym",true,true);
		} catch (InvalidKeyException | InvalidTypeException e) {
			ShowAlert.showAlert(AlertType.ERROR, "Error", "Exception!"+e.getMessage());
		}
		
		
	}
	@Override
	public void loadAgent(InputAgentDos ia1) {
		try {
			setRequiredAndWrite("projwfc","filpdos",true,true);
			
			//from dos.x
			final double mulFactor;
			if(ia1.energyUnit.equals(EnumUnitEnergy.Ry)) {mulFactor=PhysicalConstants.ryInEV;}
			else if(ia1.energyUnit.equals(EnumUnitEnergy.eV)) {mulFactor=1.0;}
			else {
				ShowAlert.showAlert(AlertType.ERROR, "Error", "Unidentified EnumUnitEnergy. Abort.");
				return;
	    	}
				
			//QE unit in eV
			andExplicitWrite("projwfc","Emax",!ia1.emax.isNull());
			if(!ia1.emax.isNull()) {setValue("projwfc","Emax",ia1.emax,mulFactor);}
			
			andExplicitWrite("projwfc","Emin",!ia1.emin.isNull());
			if(!ia1.emin.isNull()) {setValue("projwfc","Emin",ia1.emin,mulFactor);}
			
			if(!ia1.estep.isNull()) {setValue("projwfc","DeltaE",ia1.estep,mulFactor);}
			
			boolean boolAdvanced = ia1.setAdvanced;
			
			andExplicitWrite("projwfc","ngauss",boolAdvanced);
			andExplicitWrite("projwfc","degauss",boolAdvanced);
			
			if(boolAdvanced) {
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
				setValue("projwfc","ngauss",new WrapperInteger(ngauss,boolWrite));
				setValue("projwfc","degauss",ia1.degauss,mulFactor/PhysicalConstants.ryInEV);//QE unit in Ry
			}
			
			//from projwfc.x
			setValue("projwfc","lwrite_overlaps",ia1.boolLwrite);
		} catch (InvalidKeyException | InvalidTypeException e) {
			ShowAlert.showAlert(AlertType.ERROR, "Error", "Exception!"+e.getMessage());
		}
		
		
	}
	
}
