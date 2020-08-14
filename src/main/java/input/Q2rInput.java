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
import com.programconst.DefaultFileNamesQE;

import agent.InputAgentPhonon;
import core.com.error.InvalidKeyException;
import core.com.error.InvalidTypeException;
import core.com.error.ShowAlert;
import core.input.InputValueString;
import javafx.scene.control.Alert.AlertType;


public class Q2rInput extends QeInput{

	public Q2rInput() {
		super("q2r");
		sectionDict.put("input", new NameList(EnumNameList.input));
		sectionDict.get("input").setBoolRequired(true);
		
		sectionDict.get("input").addParameter("fildyn", new InputValueString("fildyn",DefaultFileNamesQE.fildyn,true));
		sectionDict.get("input").addParameter("flfrc", new InputValueString("flfrc",DefaultFileNamesQE.flfrc,true));
		sectionDict.get("input").addParameter("zasr", new InputValueString("zasr","no",false));
	}
	@Override
	public void loadAgent(InputAgentPhonon ia1) {
		try {		
			setValue("input","zasr",ia1.asr);
		} catch (InvalidKeyException | InvalidTypeException e) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
		}
	}
}
