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
import com.consts.Constants.EnumPolarizability;
import com.consts.Constants.EnumTddftUnitEnergy;
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;
import com.error.ShowAlert;
import agent.InputAgentTddft;
import agent.WrapperInteger;
import javafx.scene.control.Alert.AlertType;

public class TurboSpectrumInput extends QeInput{

	
	public TurboSpectrumInput() {
		super("turbo_spectrum");
		sectionDict.put("lr_input", new NameList(EnumNameList.lr_input));
		sectionDict.get("lr_input").setBoolRequired(true);
		
		sectionDict.get("lr_input").addParameter("itermax0", new InputValueInt("itermax0",500,true));
		sectionDict.get("lr_input").addParameter("itermax", new InputValueInt("itermax",500,false));
		sectionDict.get("lr_input").addParameter("extrapolation", new InputValueString("extrapolation","no",false));
		sectionDict.get("lr_input").addParameter("units", new InputValueInt("units",0,false));
		sectionDict.get("lr_input").addParameter("epsil", new InputValueDouble("epsil",0.02,false));
		sectionDict.get("lr_input").addParameter("start", new InputValueDouble("start",0.0,false));
		sectionDict.get("lr_input").addParameter("end", new InputValueDouble("end",2.5,false));
		sectionDict.get("lr_input").addParameter("increment", new InputValueDouble("increment",0.001,false));
		sectionDict.get("lr_input").addParameter("eels", new InputValueBoolean("eels",false,false));
		sectionDict.get("lr_input").addParameter("ipol", new InputValueInt("ipol",1,false));
	}
	
	@Override
	public void loadAgent(InputAgentTddft ia1) {

		try {		
			setValue("lr_input","itermax0",ia1.itermax0);
			setValue("lr_input","itermax",ia1.itermax);
			setValue("lr_input","extrapolation",ia1.enumExtrap);
			
			final int units;
			final boolean boolUnits=ia1.enumEUnit.isEnabled();
			switch((EnumTddftUnitEnergy)ia1.enumEUnit.getValue()) {
				case Ry:units=0;break;
				case eV:units=1;break;
				case nmpeV:units=2;break;
				default:
					units=0;
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Unknown EnumTddftUnitEnergy. Use default.");
					break;
			}
			setValue("lr_input","units",new WrapperInteger(units,boolUnits));
			setValue("lr_input","epsil",ia1.epsil);
			setValue("lr_input","start",ia1.estart);
			setValue("lr_input","end",ia1.eend);
			setValue("lr_input","increment",ia1.de);
			setValue("lr_input","eels",ia1.eels);
			
			final int ipol;
			final boolean boolIpol=ia1.enumPolar.isEnabled();
			switch((EnumPolarizability)ia1.enumPolar.getValue()) {
				case alpha_xx:ipol=1;break;
				case alpha_yy:ipol=2;break;
				case alpha_zz:ipol=3;break;
				case full:ipol=4;break;
				default:
					ipol=1;
					ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Unknown EnumPolarizability. Use default.");
					break;
			}
			setValue("lr_input","ipol",new WrapperInteger(ipol,boolIpol));
			
		} catch (InvalidKeyException | InvalidTypeException e) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
		}
	}
}
