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
import com.error.InvalidKeyException;
import com.error.InvalidTypeException;
import com.error.ShowAlert;
import com.programconst.DefaultFileNames;
import com.programconst.ProgrammingConsts;

import agent.InputAgentPhonon;
import agent.WrapperBoolean;
import agent.WrapperString;
import app.input.Kpoint;
import javafx.scene.control.Alert.AlertType;


public class MatdynInput extends QeInput{

	public MatdynInput() {
		super("matdyn");
		//amass defined in scf calculation from pw.x, no need to define here. Verified by test calculation.
		
		sectionDict.put("input", new NameList(EnumNameList.input));
		sectionDict.put(ProgrammingConsts.endPart, new Card(EnumCard.END));
		
		sectionDict.get("input").setBoolRequired(true);
		
		sectionDict.get("input").addParameter("flfrc", new InputValueString("flfrc",DefaultFileNames.flfrc,true));//needed
		sectionDict.get("input").addParameter("fldos", new InputValueString("fldos",DefaultFileNames.fldos,false));
		sectionDict.get("input").addParameter("flfrq", new InputValueString("flfrq",DefaultFileNames.flfrq,false));
		
		sectionDict.get("input").addParameter("dos", new InputValueBoolean("dos",true,true));//not QE default, so required
		sectionDict.get("input").addParameter("asr", new InputValueString("asr","no",false));
		
		sectionDict.get("input").addParameter("nk1", new InputValueInt("nk1",false));
		sectionDict.get("input").addParameter("nk2", new InputValueInt("nk2",false));
		sectionDict.get("input").addParameter("nk3", new InputValueInt("nk3",false));
		
		sectionDict.get("input").addParameter("q_in_band_form", new InputValueBoolean("q_in_band_form",false));
		sectionDict.get("input").addParameter("q_in_cryst_coord", new InputValueBoolean("q_in_cryst_coord",false));
		
		sectionDict.get(ProgrammingConsts.endPart).addParameter("body",new InputValueString("body","",false));
		 
	}
	@Override
	public void loadAgent(InputAgentPhonon ia1) {
		try {		
			boolean isDos = ia1.dos.getValue();//should not be null
			
			setValue("input","dos",ia1.dos);
			setRequiredAndWrite("input","dos",true,true);
			
			setRequiredAndWrite("input","fldos",isDos,isDos);
			setRequiredAndWrite("input","flfrq",!isDos,!isDos);
			
			setValue("input","nk1",ia1.nk1);
			setValue("input","nk2",ia1.nk2);
			setValue("input","nk3",ia1.nk3);
			
			setRequiredAndWrite("input","nk1",isDos,isDos);
			setRequiredAndWrite("input","nk2",isDos,isDos);
			setRequiredAndWrite("input","nk3",isDos,isDos);
			
			setValue("input","q_in_band_form",new WrapperBoolean(!isDos,!isDos));
			setValue("input","q_in_cryst_coord",new WrapperBoolean(!isDos,!isDos));
			
			setValue("input","asr",ia1.asr);
			
			setSectionRequired(ProgrammingConsts.endPart,!isDos);
			
			String kpointTmp = ia1.listKPoints.size()>0 ? Integer.toString(ia1.listKPoints.size())+"\n":"";
			for (int i=0;i<ia1.listKPoints.size();i++) {
				Kpoint kTmp = ia1.listKPoints.get(i);
				kpointTmp += (
							Double.toString(kTmp.getKx())
							+"  "+Double.toString(kTmp.getKy())
							+"  "+Double.toString(kTmp.getKz())
							+"  "+Integer.toString(kTmp.getNk())
							+"  !"+kTmp.getLabel()
							+"\n"
						);
			}
			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", kpointTmp);
			setValue(ProgrammingConsts.endPart,"body",new WrapperString(kpointTmp));
			
			setRequiredAndWrite(ProgrammingConsts.endPart,"body",!isDos,!isDos);
			
		} catch (InvalidKeyException | InvalidTypeException e) {
	    	ShowAlert.showAlert(AlertType.INFORMATION, "Error", "Exception!"+e.getMessage());
		}
	}
}
