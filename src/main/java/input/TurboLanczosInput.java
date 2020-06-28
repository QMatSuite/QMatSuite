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
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;
import com.error.ShowAlert;
import agent.InputAgentTddft;
import agent.WrapperInteger;
import javafx.scene.control.Alert.AlertType;

public class TurboLanczosInput extends QeInput{

	public TurboLanczosInput() {
		super("turbo_lanczos");
		sectionDict.put("lr_input", new NameList(EnumNameList.lr_input));
		sectionDict.put("lr_control", new NameList(EnumNameList.lr_control));
		sectionDict.put("lr_post", new NameList(EnumNameList.lr_post));
		
		sectionDict.get("lr_input").setBoolRequired(true);
		sectionDict.get("lr_control").addParameter("itermax", new InputValueInt("itermax",500,false));
		sectionDict.get("lr_control").addParameter("ipol", new InputValueInt("ipol",1,false));
		
	}
	@Override
	public void loadAgent(InputAgentTddft ia1) {

		try {		
			setValue("lr_control","itermax",ia1.itermax0);
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
			setValue("lr_control","ipol",new WrapperInteger(ipol,boolIpol));

		} catch (InvalidKeyException | InvalidTypeException e) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
		}
	}
}
