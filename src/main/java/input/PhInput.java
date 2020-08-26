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

import com.consts.Constants.EnumCard;
import com.consts.Constants.EnumNameList;
import com.programconst.DefaultFileNamesQE;
import com.programconst.ProgrammingConstsQE;

import agent.InputAgentPhonon;
import core.agent.WrapperString;
import core.com.error.InvalidKeyException;
import core.com.error.InvalidTypeException;
import core.com.error.ShowAlert;
import core.input.InputValueBoolean;
import core.input.InputValueDouble;
import core.input.InputValueInt;
import core.input.InputValueString;
import javafx.scene.control.Alert.AlertType;


public class PhInput extends QeInput{

	public PhInput() {
		super("ph");
		sectionDict.put("INPUTPH", new NameList(EnumNameList.INPUTPH));
		sectionDict.get("INPUTPH").setBoolRequired(true);
		sectionDict.put(ProgrammingConstsQE.endPart, new Card(EnumCard.END));
		
		sectionDict.get("INPUTPH").addParameter("outdir", new InputValueString("outdir",DefaultFileNamesQE.outDir,true));//always write
		sectionDict.get("INPUTPH").addParameter("fildyn", new InputValueString("fildyn",DefaultFileNamesQE.fildyn,true));
		sectionDict.get("INPUTPH").addParameter("tr2_ph", new InputValueDouble("tr2_ph",1E-12,false));
		sectionDict.get("INPUTPH").addParameter("ldisp", new InputValueBoolean("ldisp",false,false));
		//amass defined in scf calculation from pw.x, no need to define here. Verified by test calculation.
		sectionDict.get("INPUTPH").addParameter("nq1", new InputValueInt("nq1",false));
		sectionDict.get("INPUTPH").addParameter("nq2", new InputValueInt("nq2",false));
		sectionDict.get("INPUTPH").addParameter("nq3", new InputValueInt("nq3",false));
		
		sectionDict.get("INPUTPH").addParameter("epsil", new InputValueBoolean("epsil",false,false));
		sectionDict.get("INPUTPH").addParameter("lraman", new InputValueBoolean("lraman",false,false));
		sectionDict.get("INPUTPH").addParameter("eth_rps", new InputValueDouble("eth_rps",1E-9,false));
		sectionDict.get("INPUTPH").addParameter("eth_ns", new InputValueDouble("eth_ns",1E-12,false));
		sectionDict.get("INPUTPH").addParameter("dek", new InputValueDouble("dek",1E-3,false));	
		
		sectionDict.get(ProgrammingConstsQE.endPart).addParameter("body",new InputValueString("body","",false));
	}
	@Override
	public void loadAgent(InputAgentPhonon ia1) {

		try {		
			setValue("INPUTPH","tr2_ph",ia1.tr2_ph);

			setValue("INPUTPH","ldisp",ia1.ldisp);
			setRequiredAndWrite("INPUTPH","ldisp",true,true);//not necessary, just for clarity
			
			setValue("INPUTPH","nq1",ia1.nq1);
			setValue("INPUTPH","nq2",ia1.nq2);
			setValue("INPUTPH","nq3",ia1.nq3);
			
			setValue("INPUTPH","epsil",ia1.epsil);
			setValue("INPUTPH","lraman",ia1.lraman);
			setValue("INPUTPH","eth_rps",ia1.eth_rps);
			setValue("INPUTPH","eth_ns",ia1.eth_ns);
			setValue("INPUTPH","dek",ia1.dek);
			
			boolean boolGrid = ia1.ldisp.getValue();//should not be null
			setRequiredAndWrite("INPUTPH","nq1",boolGrid,boolGrid);
			setRequiredAndWrite("INPUTPH","nq2",boolGrid,boolGrid);
			setRequiredAndWrite("INPUTPH","nq3",boolGrid,boolGrid);
			
			boolean boolRaman = ia1.lraman.getValue();//should not be null
			andExplicitWrite("INPUTPH", "epsil", !boolGrid);
			andExplicitWrite("INPUTPH", "lraman", !boolGrid);
			andExplicitWrite("INPUTPH", "eth_rps", (!boolGrid)&&boolRaman);
			andExplicitWrite("INPUTPH", "eth_ns", (!boolGrid)&&boolRaman);
			andExplicitWrite("INPUTPH", "dek", (!boolGrid)&&boolRaman);
			
			setSectionRequired(ProgrammingConstsQE.endPart,!boolGrid);
			if(!boolGrid) {
				setValue(ProgrammingConstsQE.endPart,"body",new WrapperString("0 0 0"));
				setRequiredAndWrite(ProgrammingConstsQE.endPart,"body",true,true);
			}
			else {
				setValue(ProgrammingConstsQE.endPart,"body",new WrapperString(""));
				setRequiredAndWrite(ProgrammingConstsQE.endPart,"body",false,false);
			}


		} catch (InvalidKeyException | InvalidTypeException e) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
		}
	}
}
