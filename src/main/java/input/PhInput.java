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
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;
import com.error.ShowAlert;

import agent.InputAgentPhonon;
import javafx.scene.control.Alert.AlertType;


public class PhInput extends QeInput{

	public PhInput() {
		super("ph");
		sectionDict.put("INPUTPH", new NameList(EnumNameList.INPUTPH));
		sectionDict.get("INPUTPH").setBoolRequired(true);
		
		sectionDict.get("INPUTPH").addParameter("tr2_ph", new InputValueDouble("tr2_ph",1E-12,false));
		sectionDict.get("INPUTPH").addParameter("ldisp", new InputValueBoolean("ldisp",true,true));//always write, user cannot change
		//amass defined in scf calculation from pw.x, no need to define here
		sectionDict.get("INPUTPH").addParameter("nq1", new InputValueInt("nq1",true));
		sectionDict.get("INPUTPH").addParameter("nq2", new InputValueInt("nq2",true));
		sectionDict.get("INPUTPH").addParameter("nq3", new InputValueInt("nq3",true));
	}
	@Override
	public void loadAgent(InputAgentPhonon ia1) {

		try {		
			setValue("INPUTPH","tr2_ph",ia1.tr2_ph);
			//setRequiredAndWrite("lr_control","itermax",true,true);//from QE, not necessary, but in practice yes, otherwise give error
			
			setValue("INPUTPH","nq1",ia1.nq1);
			setValue("INPUTPH","nq2",ia1.nq2);
			setValue("INPUTPH","nq3",ia1.nq3);

		} catch (InvalidKeyException | InvalidTypeException e) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
		}
	}
}
