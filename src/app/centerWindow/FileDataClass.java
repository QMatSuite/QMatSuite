package app.centerWindow;

import java.util.ArrayList;

public class FileDataClass {
	private ArrayList<ArrayList<Double>> energyArray;//Ry
	private ArrayList<Double> fermiLevel;//eV
	private ArrayList<Double> homoLevel;//eV
	
	public int nstep=1;
	public boolean isJobDone=false;
	public boolean hasScf=false;//true when there exist scf steps inside the output file. Not necessary means that it is a scf calculation
	public boolean hasScfFinished=false;
	public boolean isMD=false;
	public boolean isMDFinished=false;
	public boolean isOpt=false;
	public boolean isOptFinished=false;
	public boolean isNscf=false;
	public boolean isNscfFinished=false;
	
	public FileDataClass() {
		energyArray = new ArrayList<ArrayList<Double>>();
		fermiLevel = new ArrayList<Double>();
		homoLevel = new ArrayList<Double>();
	}
	public void clearAll() {
		clearEnergyArray();
	}
	public void clearEnergyArray() {
		for(ArrayList<Double> ard:energyArray) {
			if(ard!=null) {ard.clear();}
		}
		energyArray.clear();
		fermiLevel.clear();
		homoLevel.clear();
		nstep=1;
		isJobDone=false;
		hasScf=false;hasScfFinished=false;isMD=false;isMDFinished=false;isOpt=false;isOptFinished=false;
		isNscf=false;isNscfFinished=false;
	}
	public void addTotalEnergy(double ene, boolean isFinal) {
		//here, ene and isFinal are primitive types that CANNOT be null
		if(energyArray==null) {energyArray = new ArrayList<ArrayList<Double>>();}//shouldn't happen
		if(energyArray.isEmpty()) {energyArray.add(new ArrayList<Double>());}
		energyArray.get(energyArray.size()-1).add(ene);
		if(isFinal) {energyArray.add(new ArrayList<Double>());}
	}
	public ArrayList<ArrayList<Double>> getEnergyArray(){
		return this.energyArray;
	}
	public void setFermi(double fl) {
		fermiLevel.add(fl);
	}
	public void setHomo(double hm) {
		homoLevel.add(hm);
	}
	public String toString() {
		String strTmp = "";
		Integer cnt = 0;
		//calculation type
		strTmp+="Detected calculation type:";
		if(nstep==1 && hasScf) {strTmp+="SCF,";}
		if(isMD) {strTmp+="MD,";}
		if(isOpt) {strTmp+="Optimization,";}
		if(isNscf) {strTmp+="NSCF,";}
		strTmp+="\n";

		//finished or not
		if(hasScf) {strTmp+=(hasScfFinished?"SCF finished.":"SCF not finished.")+"\n";}
		if(isMD) {strTmp+=(isMDFinished?"MD finished.":"MD not finished.")+"\n";}
		if(isOpt) {strTmp+=(isOptFinished?"Optimization finished.":"Optimization not finished.")+"\n";}
		if(isNscf) {strTmp+=(isNscfFinished?"NSCF finished.":"NSCF not finished.")+"\n";}
		
		//the whole job finished or not (last line of the output file)
		strTmp+=(isJobDone?"Job done.\n":"Job not done yet.\n");
		
		//total energy
		strTmp+="Total energy (Ry):";
		for(ArrayList<Double> ard:energyArray) {
			if(ard!=null) {
				cnt++;
				if(ard.isEmpty()) {continue;}
				strTmp+=("Step "+cnt.toString()+": ");
				for(Double val:ard) {
					if(val!=null) {strTmp+=(val.toString()+",");}
				}
				strTmp+="\n";
			}
		}
		
		//Fermi
		strTmp+="Fermi energy: ";
		if(fermiLevel.isEmpty()) {strTmp+="Unknown\n";}
		else {
			for(Double val:fermiLevel) {
				if(val!=null) {strTmp+=(val.toString()+",");}
			}
			strTmp+=" eV\n";
		}
		//HOMO
		strTmp+="Highest occupied level: ";
		if(homoLevel.isEmpty()) {strTmp+="Unknown\n";}
		else {
			for(Double val:homoLevel) {
				if(val!=null) {strTmp+=(val.toString()+",");}
			}
			strTmp+=" eV\n";
		}
		
		return strTmp;
	}
}
